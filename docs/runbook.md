# Operational Runbook

This document provides procedures for deploying, operating, monitoring, and troubleshooting the Cortex Knowledge Assistant in a production-like environment.

## 1. Components

| Component          | Purpose                          | Criticality |
| ------------------ | -------------------------------- | ----------- |
| API (FastAPI)      | Serves /query, /health, /metrics | High        |
| Qdrant             | Vector similarity search         | High        |
| Redis (optional)   | Cache for answers                | Medium      |
| Ollama             | Local LLM runtime                | High        |
| Prometheus/Grafana | Metrics scrape & dashboards      | Medium      |
| OTLP Collector     | Tracing export endpoint          | Medium      |

## 2. Environment Variables (Prefix CKA\_)

| Variable                      | Description                          | Default     |
| ----------------------------- | ------------------------------------ | ----------- | ---- |
| CKA_API_KEY                   | API key protecting /query            | (empty)     |
| CKA_USE_QDRANT                | Enable real Qdrant retriever         | false       |
| CKA_USE_REDIS                 | Use Redis cache adapter              | false       |
| CKA_ENABLE_TRACING            | Enable OpenTelemetry instrumentation | false       |
| CKA_RATE_LIMIT_QPM            | Requests per minute per key          | 120         |
| CKA_CONVERSATION_MAX_TURNS    | Context turns retained               | 5           |
| CKA_OLLAMA_MODEL              | LLM model id                         | llama3.2:3b |
| CKA_LLM_PROVIDER              | LLM provider (Fake                   | HF)         | Fake |
| HF_API_KEY                    | Hugging Face token (if HF)           | (empty)     |
| CKA_ENABLE_STREAMING          | Enable SSE streaming endpoint        | false       |
| CKA_HTTPS_ENABLED             | Enable CSP/HSTS headers              | false       |
| CKA_CSP_POLICY                | CSP policy when HTTPS enabled        | strict self |
| CKA_MAX_INPUT_TOKENS          | Input token guard rail               | 2048        |
| CKA_MAX_OUTPUT_TOKENS         | Output token guard rail              | 512         |
| CKA_RATE_LIMIT_BURST          | Additional burst allowance           | 0           |
| CKA_RATE_LIMIT_WINDOW_SECONDS | Rate limit window seconds            | 60          |

## 3. Deployment Steps

1. Provision infrastructure (container runtime, network, storage).
2. Secure secrets (API key, Qdrant key) via secret manager.
3. Build image: `docker build -f docker/Dockerfile.api -t cortex-ka:$(git rev-parse --short HEAD) .`
4. Run `docker compose -f docker/compose.yml up -d` (ensure Qdrant & Redis health).
5. Initialize collection: `make qdrant-init` (once per environment).
6. Ingest documents: `make ingest` (idempotent; re-run after adding new source docs).

## 4. Health & Readiness

- Liveness: `/health` returns `{status: ok}`.
- Metrics: `/metrics` (Prometheus format). Configure scrape interval 15s.
- Traces: verify spans received in collector (e.g., Jaeger/Tempo) when tracing enabled.
- HF provider: `/health` includes `provider` and `provider_ok`; `hint` present when unhealthy.

### 4.1 HF Provider Health Hints

| Status Code | Meaning                                   | Operator Action                                 |
| ----------- | ----------------------------------------- | ----------------------------------------------- |
| 401         | Unauthorized API key                      | Rotate/check `HF_API_KEY`; ensure not expired   |
| 403         | Forbidden / quota or access restriction   | Check Hugging Face account limits / permissions |
| 404         | Model not found or private                | Verify `CKA_HF_MODEL` spelling / permissions    |
| 410         | Model deprecated                          | Select a supported alternative; update ADR-0006 |
| 503         | Model loading / transient infra condition | Wait; if persistent >2m consider smaller model  |

Health check treats 200 as healthy and 503 as "loading" (still considered acceptable). Other statuses will surface `hint` and set `provider_ok=false`.

## 5. Scaling

- Horizontal API scaling behind load balancer (stateless except in-memory conversation; use Redis or external store for shared memory if scaling >1 instance).
- Ensure Qdrant configured with appropriate replication/sharding for volume.
- Enable Redis for shared cache across replicas (`CKA_USE_REDIS=true`).

## 6. Logging

- Structured JSON to STDOUT (ingest into ELK / Loki).
- Include `X-Request-ID` for correlation. Upstream gateway should pass or generate this header.

## 7. Metrics (Key)

| Metric                           | Type      | Description                       |
| -------------------------------- | --------- | --------------------------------- |
| cka_http_requests_total          | Counter   | Requests by endpoint/status class |
| cka_http_request_latency_seconds | Histogram | Per-endpoint latency              |
| cka_query_latency_seconds        | Histogram | Latency specifically for /query   |
| cka_retrieved_chunks_count       | Histogram | Distribution of retrieved chunks  |

Alert examples:

- High 5xx ratio (>5% over 5m) for /query.
- p95 `cka_http_request_latency_seconds{endpoint="/query"}` > threshold.

## 8. Rate Limiting

- Keyed by API key or session id. Adjust `CKA_RATE_LIMIT_QPM`. For distributed environment, move rate limiting to API gateway or implement Redis token buckets.

Operational toggles:

- Increase `CKA_RATE_LIMIT_QPM` cautiously; match infra capacity.
- Use `CKA_RATE_LIMIT_BURST` for short spikes without raising sustained QPM.
- Adjust `CKA_RATE_LIMIT_WINDOW_SECONDS` for more/less smoothing.

## 9. Token Budgeting & Guard Rails

- Guard rails approximate tokens; if improved control required, implement model-specific max tokens and summarization fallback (see backlog).

## 10. Security Hardening Checklist

| Item              | Status                | Notes                                         |
| ----------------- | --------------------- | --------------------------------------------- |
| API key auth      | Implemented           | Optional var CKA_API_KEY                      |
| Rate limiting     | Implemented           | In-memory + keyed; externalize for multi-node |
| Security headers  | Basic set             | Add CSP/HSTS at reverse proxy                 |
| Dependency audit  | CI pip-audit gating   | Fails on HIGH/CRITICAL                        |
| Secrets in code   | None                  | Verified via review                           |
| Tracing & metrics | Enabled (opt/tracing) | Prometheus & OTLP                             |

## 11. Backup & Recovery

- Qdrant: snapshot collections (volume-level backup; schedule nightly).
- Redis: if used for cache only, backup optional; if extended for conversation memory, enable AOF persistence & backup daily.
- Config: store environment variable definitions in infra-as-code (Terraform, etc.).

## 12. Incident Response Playbook

| Symptom                      | Likely Cause                      | Action                                                                         |
| ---------------------------- | --------------------------------- | ------------------------------------------------------------------------------ |
| 5xx spike                    | External LLM/Qdrant outage        | Check `/health`, switch to Fake provider temporarily (`CKA_LLM_PROVIDER=Fake`) |
| Latency increase             | Qdrant saturation / provider slow | Reduce `CKA_QDRANT_TOP_K`, enable Redis cache, verify provider status          |
| Memory growth                | Large conversation history        | Lower `CKA_CONVERSATION_MAX_TURNS`; if scaling horizontally use shared store   |
| Frequent 401                 | Misconfigured API key / header    | Confirm env value & header name, check proxy stripping custom headers          |
| Frequent 429                 | Abuse / insufficient quota        | Inspect `Retry-After`; raise QPM or introduce gateway limit tier               |
| Timeouts to HF               | External API degradation          | Fallback to Fake; monitor provider status dashboard                            |
| High error rate in ingestion | Embedding model load fail         | Validate model path/container resources                                        |
| Missing CSP/HSTS             | HTTPS flag off / proxy config     | Set `CKA_HTTPS_ENABLED=true` only behind TLS; verify ingress rewrites          |
| Sensitive data in logs       | Scrubber bypass pattern           | Audit samples; update scrub regex & redeploy                                   |

### 12.1 Log Scrubbing Verification

1. Trigger a test request with a dummy header `Authorization: Bearer TESTTOKEN123`.
2. Inspect logs; token must appear as `<redacted>`.
3. If not redacted, update scrub processor patterns and redeploy.

### 12.2 Rate Limit Spike Handling

1. Confirm via metrics: high 429 count.
2. Validate legitimate traffic vs abuse using API key distribution.
3. Short-term: increase `CKA_RATE_LIMIT_BURST`; long-term: implement gateway-level quotas.

### 12.3 Timeout Investigation

1. Check histogram p95 in `/metrics` for `/query`.
2. If retrieval dominates, lower `CKA_QDRANT_TOP_K`.
3. If generation dominates, consider smaller model or enabling summarization backlog feature.

### 12.4 Rollback Procedure

1. Identify last known good version (from `/version` endpoint logs or tags).
2. Re-deploy previous image tag (immutable build recommended).
3. Run smoke test (`/health`, `/version`, one `/query`).
4. Announce rollback and open postmortem.

## 13. Change Management

- Follow Gitflow: feature branches -> PR -> CI pass -> merge to develop -> release to main.
- Tag releases `vMAJOR.MINOR.PATCH` and update CHANGELOG.

## 14. Performance Tuning Levers

- Reduce `qdrant_top_k` for faster retrieval.
- Add embedding batch size (future optimization) to minimize overhead.
- Enable Redis cache for hot queries.
- Add summarization of excess context to reduce prompt length.

Ambiguous defaults documented:

- HTTPS disabled locally (`CKA_HTTPS_ENABLED=false`) to reduce dev friction; production must enable.
- Fake LLM default chosen to guarantee deterministic CI; HF used only when explicitly configured.
- Rate limit window 60s selected for balance between burst absorption and fairness.

## 15. Decommission Procedure

1. Disable ingestion jobs.
2. Drain API traffic (remove from LB).
3. Snapshot Qdrant volume.
4. Archive logs & metrics (compliance retention).
5. Destroy infrastructure via IaC.

---

This runbook is living documentation; update alongside operational changes and new ADRs.
