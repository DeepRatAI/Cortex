"""FastAPI presentation layer for Cortex KA."""

from __future__ import annotations
from fastapi import FastAPI, Header, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
import uuid
import os
from pydantic import BaseModel
from ..application.rag_service import RAGService
from ..application.metrics import (
    http_requests_total,
    query_latency_seconds,
    retrieved_chunks,
    http_request_latency_seconds,
    active_model_info,
)
from ..infrastructure.retriever_stub import StubRetriever
from ..infrastructure.retriever_qdrant import QdrantRetriever
from ..infrastructure.memory_cache import InMemoryCache
from ..infrastructure.redis_cache import RedisCache
from ..logging import logger
from ..domain.ports import LLMPort
from ..config import settings
from ..infrastructure.memory_store import RateLimiter, ConversationMemory
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import time
import os as _os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from starlette.responses import StreamingResponse
from ..build_info import APP_VERSION, GIT_SHA, BUILD_TIME_UTC
from ..infrastructure.llm_hf import HFLLM  # to be created
from ..application.dlp import enforce_dlp


app = FastAPI(title="Cortex Knowledge Assistant", version=APP_VERSION)
origins = [o.strip() for o in (settings.cors_origins or "").split(",") if o.strip()]
if not origins:
    origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tracing (optional): enable via CKA_ENABLE_TRACING=true
if _os.getenv("CKA_ENABLE_TRACING", "").lower() in {
    "1",
    "true",
    "yes",
}:  # pragma: no cover
    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    exporter = OTLPSpanExporter()  # Exports to OTLP endpoint (defaults to env vars)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    FastAPIInstrumentor.instrument_app(app)


@app.middleware("http")
async def https_security_headers(request: Request, call_next):  # pragma: no cover
    response = await call_next(request)
    https_flag = settings.https_enabled or os.getenv(
        "CKA_HTTPS_ENABLED", ""
    ).lower() in {"1", "true", "yes"}
    if https_flag:
        # HSTS (only under HTTPS)
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload"
        )
        # CSP
        response.headers.setdefault("Content-Security-Policy", settings.csp_policy)
    return response


@app.middleware("http")
async def security_headers(request: Request, call_next):  # pragma: no cover
    """Add basic security headers to responses.

    Note: In production behind TLS/ingress, consider HSTS and stricter CSP.
    """
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


@app.middleware("http")
async def add_request_id(request: Request, call_next):  # pragma: no cover
    req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = req_id
    start = time.perf_counter()
    path = request.url.path
    method = request.method
    # Capture basic caller fingerprint for observability; do not treat it as a
    # strong identity signal.
    client_host = request.client.host if request.client else "unknown"

    logger.info(
        "http_request_start",
        request_id=req_id,
        path=path,
        method=method,
        client_host=client_host,
    )

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as exc:  # Capture unhandled errors for metrics
        status_code = 500
        logger.error(
            "http_request_exception",
            request_id=req_id,
            path=path,
            method=method,
            status_code=status_code,
            error=str(exc),
        )
        raise exc
    finally:
        elapsed = time.perf_counter() - start
        # status class e.g. 2xx
        status_class = f"{status_code // 100}xx"
        http_requests_total.labels(endpoint=path, status_class=status_class).inc()
        http_request_latency_seconds.labels(endpoint=path).observe(elapsed)
        logger.info(
            "http_request_end",
            request_id=req_id,
            path=path,
            method=method,
            status_code=status_code,
            elapsed_seconds=elapsed,
        )
    response.headers["X-Request-ID"] = req_id
    return response


class QueryRequest(BaseModel):
    """Incoming query payload."""

    query: str
    session_id: str | None = None
    # NOTE: subject_id is no longer accepted from the client for security
    # reasons. Client identity is derived from authenticated user context
    # (current_user.allowed_subject_ids) instead of trusting headers/body.


class QueryResponse(BaseModel):
    """Outgoing answer structure."""

    answer: str
    used_chunks: list[str]
    session_id: str | None = None
    citations: list[dict] | None = None


class _FakeLLM(LLMPort):
    """Simple deterministic LLM used for tests to avoid external dependency."""

    def generate(self, prompt: str) -> str:  # type: ignore[override]
        _ = prompt  # acknowledge param
        return "This is a synthesized answer based on internal procedures."


class CurrentUser(BaseModel):
    """Authenticated user context used for authorization decisions.

    In a real deployment this would be populated from a JWT/OIDC token or
    an identity provider. For this demo, we keep an in-memory mapping from
    redacted_answer = enforce_dlp(answer_obj.answer, user=current_user)
    access control.

    The ``dlp_level`` field is a coarse-grained hint for DLP behaviour:

    - "standard": default level; full DLP redaction is applied.
    - "privileged": callers are trusted to handle PII and may see
        unredacted answers (for example, internal backoffice tools in a
        tightly controlled network).

    Backends integrating with a real IdP can derive this from roles or
    claims (e.g. "role=backoffice" or specific entitlements).
    """

    user_id: str
    allowed_subject_ids: list[str]
    dlp_level: str = "standard"


_DEMO_USER_MAP: dict[str, CurrentUser] = {
    # Example: API key "demo-key-cli-81093" is bound to customer CLI-81093.
    # In production, this should come from an identity provider / IAM system.
    "demo-key-cli-81093": CurrentUser(
        user_id="user-cli-81093",
        allowed_subject_ids=["CLI-81093"],
        dlp_level="standard",
    ),
    # Example of a privileged operator with access to the same subject but
    # with relaxed DLP. This key is provided for demonstration and tests; it
    # should never be used in unconstrained environments.
    "demo-key-cli-81093-ops": CurrentUser(
        user_id="ops-cli-81093",
        allowed_subject_ids=["CLI-81093"],
        dlp_level="privileged",
    ),
}


def get_current_user(x_cka_api_key: str | None = Header(default=None)) -> CurrentUser:
    """Authenticate request and return current user context.

    Today this uses a simple API key mapping for demo purposes. The structure
    is intentionally compatible with a future JWT/OIDC-based implementation,
    where user_id and allowed_subject_ids would come from token claims.
    """

    configured_api_key = os.getenv("CKA_API_KEY") or settings.api_key
    if configured_api_key and x_cka_api_key != configured_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Demo multi-tenant mapping: bind per-user allowed_subject_ids.
    # If no mapping is found, deny access by default.
    if not x_cka_api_key or x_cka_api_key not in _DEMO_USER_MAP:
        raise HTTPException(status_code=403, detail="Forbidden")
    return _DEMO_USER_MAP[x_cka_api_key]


def _select_llm():
    provider = os.getenv("CKA_LLM_PROVIDER", settings.llm_provider).strip()
    # In confidential retrieval mode we forbid Fake LLMs and require a
    # real provider (currently HF). This is a hard guardrail intended for
    # banking-like deployments: running with Fake while this flag is true
    # is considered a configuration error.
    if settings.confidential_retrieval_only and provider.lower() == "fake":
        raise RuntimeError(
            "confidential_retrieval_only is enabled but llm_provider is 'Fake'. "
            "Please configure a real provider (e.g. HF)."
        )

    if provider.lower() == "hf":
        key = os.getenv("HF_API_KEY") or settings.hf_api_key
        if not key:
            # No key available: gracefully fallback to Fake for dev
            (logger if isinstance(logger, object) else None)
            return _FakeLLM()
        return HFLLM(api_key=key, model=os.getenv("CKA_HF_MODEL") or settings.hf_model)
    # default: Fake
    return _FakeLLM()


def _select_retriever():
    if os.getenv("CKA_USE_QDRANT", "").lower() in {"1", "true", "yes"}:
        return QdrantRetriever()
    return StubRetriever()


# Instantiate service after evaluating environment flags; this allows tests to set
# env vars prior to import or reloading without triggering external connections.
_cache = InMemoryCache()
if os.getenv("CKA_USE_REDIS", "").lower() in {"1", "true", "yes"}:
    try:  # pragma: no cover - depends on external service
        _cache = RedisCache()
    except Exception:
        _cache = InMemoryCache()
_service = RAGService(
    retriever=_select_retriever(),
    llm=_FakeLLM() if "PYTEST_CURRENT_TEST" in os.environ else _select_llm(),
    cache=_cache,
)
_rate_limiter = RateLimiter(settings.rate_limit_qpm)
_memory = ConversationMemory(settings.conversation_max_turns)


@app.post("/query", response_model=QueryResponse)
def query_rag(
    payload: QueryRequest,
    x_cka_api_key: str | None = Header(default=None),
    _x_cka_subject_id: str | None = Header(default=None),  # deprecated for security
    current_user: CurrentUser = Depends(get_current_user),
    request: Request = None,
) -> QueryResponse:
    """Handle a RAG query and return an answer.

    Args:
        payload: QueryRequest with the user question.
    Returns:
        QueryResponse containing generated answer and chunk IDs.
    """
    # Input validation: length and basic sanitization
    q = (payload.query or "").strip()
    if not q:
        raise HTTPException(status_code=422, detail="Query must not be empty")
    if len(q) > 2000:
        raise HTTPException(status_code=413, detail="Query too long")

    # Establish session id first (used for keyed rate limiting)
    session_id = payload.session_id or "default"
    # Rate limiting: keyed by API key if present else session id
    limiter_key = x_cka_api_key or session_id or "global"
    if not _rate_limiter.allow(key=limiter_key):
        # Consistent body and Retry-After
        retry_after = 1
        try:
            retry_after = getattr(_rate_limiter, "retry_after", lambda k: 1)(
                limiter_key
            )
        except Exception:
            pass
        headers = {"Retry-After": str(retry_after)}
        raise HTTPException(status_code=429, detail="rate_limited", headers=headers)

    # If tests or runtime toggled fake flag post-start, refresh LLM.
    if os.getenv("CKA_FAKE_LLM", "").lower() in {"1", "true", "yes"}:
        _service._llm = _FakeLLM()  # type: ignore[attr-defined]
    # Optionally enrich with conversation context (append last turns)
    history = _memory.history(session_id)
    if history:
        # Lightweight augmentation: prepend previous Q/A as bullets
        past = "\n".join(f"- Q: {q}\n- A: {a}" for q, a in history)
        payload.query = f"Previous context (most recent first):\n{past}\n\nCurrent question: {payload.query}"

    start = time.perf_counter()
    # Derive subject_id from authenticated user context (multi-tenant control).
    # For now we support a single id_cliente per user in this demo; in a real
    # system the subject would be chosen explicitly by the client within the
    # user's allowed_subject_ids.
    if not current_user.allowed_subject_ids:
        raise HTTPException(status_code=403, detail="No customer scope assigned")
    subject_id = current_user.allowed_subject_ids[0]

    # Enforce that subject_id always comes from server-side user context and
    # never directly from client headers/body to avoid tenant breakout.
    answer_obj = _service.answer(payload.query, subject_id=subject_id)
    _memory.add_turn(session_id, payload.query, answer_obj.answer)
    duration = time.perf_counter() - start
    req_id = getattr(getattr(request, "state", object()), "request_id", None)
    safe_logger = logger.bind(request_id=req_id) if req_id else logger
    # Log only the query and user id; avoid including raw PII from context.
    safe_logger.info(
        "query_answered",
        query=payload.query,
        user_id=current_user.user_id,
        subject_id=subject_id,
    )
    # Metrics
    query_latency_seconds.observe(duration)
    retrieved_chunks.observe(len(answer_obj.used_chunks))
    # Apply the central DLP facade before returning to clients. Today this
    # delegates to redact_pii, but enforce_dlp is the single governance point
    # for future, stricter policies. It also honours the current_user.dlp_level
    # hint, allowing privileged operators to bypass redaction when explicitly
    # configured.
    redacted_answer = enforce_dlp(answer_obj.answer, user=current_user)
    return QueryResponse(
        answer=redacted_answer,
        used_chunks=answer_obj.used_chunks,
        session_id=session_id,
        citations=answer_obj.citations,
    )


@app.get("/health")
def health() -> dict:
    provider = os.getenv("CKA_LLM_PROVIDER", settings.llm_provider).strip().lower()
    if provider != "hf":
        return {"status": "ok", "provider": provider, "provider_ok": True}

    # HF diagnostics isolated to reduce complexity
    llm = _select_llm()
    try:
        provider_ok = getattr(llm, "healthy", lambda: False)()
    except Exception:
        return {
            "status": "ok",
            "provider": provider,
            "provider_ok": False,
            "hint": "HF provider exception during health check",
        }

    if provider_ok:
        active_model = getattr(llm, "model", None)
        try:
            if active_model:
                active_model_info.labels(provider="hf", model=active_model).set(1)
        except Exception:
            pass
        return {
            "status": "ok",
            "provider": provider,
            "provider_ok": True,
            "active_model": active_model,
        }

    # Build hint map
    if not (os.getenv("HF_API_KEY") or settings.hf_api_key):
        hint = "HF_API_KEY missing"
    else:
        last_err_raw = getattr(llm, "_last_error", None)
        last_err = str(last_err_raw) if last_err_raw is not None else ""
        mapping: dict[str, str] = {
            "unauthorized": "HF unauthorized (401): check HF_API_KEY",
            "forbidden": "HF forbidden (403): check account limits/permissions",
            "model_not_found": "HF model 404: verify CKA_HF_MODEL spelling/access",
            "model_gone": "HF model 410: deprecated; pick an alternative",
            "loading": "HF model loading (503): transient; retry shortly",
        }
        hint = mapping.get(
            last_err, "HF endpoint not healthy (loading or error). See runbook."
        )
    active_model = getattr(llm, "model", None)
    try:
        if active_model:
            active_model_info.labels(provider="hf", model=active_model).set(0)
    except Exception:
        pass
    return {
        "status": "ok",
        "provider": provider,
        "provider_ok": False,
        "hint": hint,
        "active_model": active_model,
    }


@app.get("/metrics")
def metrics() -> Response:
    payload = generate_latest()
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)


@app.get("/version")
def version() -> dict:
    return {
        "git_sha": GIT_SHA,
        "build_time": BUILD_TIME_UTC,
        "app_version": APP_VERSION,
    }


@app.get("/chat/stream")
def chat_stream(
    q: str = "",
    x_cka_api_key: str | None = Header(default=None),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Streaming chat endpoint (Server-Sent Events).

    This endpoint is gated by the same authentication and multi-tenant
    controls as /query. It is intentionally disabled by default and must be
    explicitly enabled via CKA_ENABLE_STREAMING or settings.enable_streaming.
    """

    if not (
        os.getenv("CKA_ENABLE_STREAMING", "").lower() in {"1", "true", "yes"}
        or settings.enable_streaming
    ):
        raise HTTPException(status_code=404, detail="Streaming disabled")

    # Derive subject_id from authenticated user context, mirroring /query.
    if not current_user.allowed_subject_ids:
        raise HTTPException(status_code=403, detail="No customer scope assigned")
    subject_id = current_user.allowed_subject_ids[0]

    # Simple rate limiting keyed by API key (same as /query)
    limiter_key = x_cka_api_key or subject_id
    if not _rate_limiter.allow(key=limiter_key):
        raise HTTPException(status_code=429, detail="rate_limited")

    answer_obj = _service.answer(q, subject_id=subject_id)
    redacted_answer = enforce_dlp(answer_obj.answer)

    def _iter_stream():
        # Very simple token streaming: split by space and send as SSE events.
        for token in redacted_answer.split(" "):
            yield f"data: {token}\n\n"

    return StreamingResponse(_iter_stream(), media_type="text/event-stream")
