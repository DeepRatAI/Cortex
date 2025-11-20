"""Application service orchestrating retrieval + generation."""

from __future__ import annotations
from ..domain.ports import RetrieverPort, LLMPort, CachePort
from ..domain.models import Answer
from ..logging import logger
from .prompt_builder import build_prompt

try:  # Optional dependency for better token estimation
    import tiktoken  # type: ignore
except Exception:  # pragma: no cover
    tiktoken = None


class RAGService:
    """Coordinates retrieval and LLM generation with caching.

    Args:
        retriever: Adapter implementing semantic retrieval.
        llm: Adapter implementing prompt completion.
        cache: Adapter implementing answer caching.

    Security note:
        The `subject_id` parameter is used to scope retrieval to a specific
        customer/tenant (id_cliente) at the vector-store level. Callers must
        ensure that this value is derived from authenticated user context
        (e.g. current_user.allowed_subject_ids) rather than directly trusting
        client-provided headers to avoid cross-tenant data leakage.
    """

    def __init__(
        self, retriever: RetrieverPort, llm: LLMPort, cache: CachePort
    ) -> None:
        self._retriever = retriever
        self._llm = llm
        self._cache = cache

    def answer(
        self,
        query: str,
        subject_id: str | None = None,
        *,
        regulatory_strict: bool = False,
    ) -> Answer:
        """Retrieve chunks, build prompt, invoke LLM, return structured answer.

        When `regulatory_strict` is True, the service will avoid hallucinating
        answers in the absence of strong retrieval signal and instead return a
        safe fallback message. This is particularly important for banking /
        compliance scenarios where "no answer" is preferable to an invented
        regulation or policy.
        """
        # Cache is scoped by both query and subject_id to avoid cross-tenant
        # collisions (different clients issuing the same question) and to
        # distinguish between calls with and without retrieval context.
        cache_key = f"{subject_id or 'anon'}::{query}::strict={regulatory_strict}"
        cached = self._cache.get_answer(cache_key)
        if cached:
            logger.info("cache_hit", query=query, subject_id=subject_id)
            return Answer(
                answer=cached,
                query=query,
                used_chunks=[],
                citations=[],
                max_pii_sensitivity=None,
            )

        retrieval = self._retriever.retrieve(query, k=5, subject_id=subject_id)
        context_blocks = [c.text for c in retrieval.chunks]

        # Coarse-grained PII sensitivity summary for observability. We derive
        # this from the per-chunk `pii_sensitivity` labels propagated by the
        # retriever so that downstream components can reason about the overall
        # sensitivity of the evidence used to produce the answer.
        max_pii_sensitivity: str | None = None

        # In regulatory-strict mode, if there is no retrieved context we avoid
        # calling the LLM and instead return a conservative message. This
        # reduces the risk of hallucinated answers to compliance questions.
        if regulatory_strict and not context_blocks:
            logger.info(
                "regulatory_strict_no_context",
                query=query,
                subject_id=subject_id,
            )
            safe_answer = (
                "No se encontraron documentos de soporte para responder a esta "
                "consulta. Para temas regulatorios o de cumplimiento, consulte "
                "las políticas oficiales del banco o al área correspondiente."
            )
            self._cache.set_answer(cache_key, safe_answer)
            return Answer(
                answer=safe_answer,
                query=query,
                used_chunks=[],
                citations=[],
                max_pii_sensitivity=None,
            )
        prompt = build_prompt(query, context_blocks)
        # Approximate token budgeting (simple heuristic):
        max_tokens = 2048
        if tiktoken:
            try:
                enc = tiktoken.get_encoding("cl100k_base")
                tok_count = len(enc.encode(prompt))
            except Exception:  # pragma: no cover
                tok_count = len(prompt) // 4
        else:
            tok_count = len(prompt) // 4  # crude char->token heuristic
        if tok_count > max_tokens:
            logger.info("prompt_truncate", original_tokens=tok_count)
            # Trim longest tail: keep header & first chunks proportionally
            # Fallback simple strategy: slice characters to 4*max_tokens
            prompt = prompt[: max_tokens * 4]

        # Compute max PII sensitivity before invoking the LLM.
        def _level(label: str | None) -> int:
            if label is None:
                return 0
            v = label.lower()
            if v == "none":
                return 0
            if v == "medium":
                return 1
            if v == "high":
                return 2
            # Unknown labels are treated conservatively as medium.
            return 1

        for chunk in retrieval.chunks:
            if chunk.pii_sensitivity is None:
                continue
            if max_pii_sensitivity is None:
                max_pii_sensitivity = chunk.pii_sensitivity
                continue
            if _level(chunk.pii_sensitivity) > _level(max_pii_sensitivity):
                max_pii_sensitivity = chunk.pii_sensitivity

        logger.info(
            "llm_invoke",
            query=query,
            chunks=len(retrieval.chunks),
            max_pii_sensitivity=max_pii_sensitivity,
        )
        output = self._llm.generate(prompt)
        self._cache.set_answer(cache_key, output)
        citations = [{"id": c.id, "source": c.source} for c in retrieval.chunks]
        return Answer(
            answer=output,
            query=query,
            used_chunks=[c.id for c in retrieval.chunks],
            citations=citations,
            max_pii_sensitivity=max_pii_sensitivity,
        )
