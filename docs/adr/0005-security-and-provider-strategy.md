# ADR 0005: Security & Provider Strategy

Date: 2025-11-10

## Status

Accepted

## Context

We need a security posture appropriate for enterprise environments and a flexible LLM provider strategy that supports local testing, CI determinism, and production connectivity to external providers when explicitly configured.

Key drivers:

- Avoid hard dependencies on external services during tests/CI.
- Enable CSP/HSTS only in HTTPS deployments while keeping local DX smooth.
- Provide traceable build metadata (/version) for auditability.
- Allow multiple LLM providers via configuration (Fake for tests, HF when HF_API_KEY is present), and add guardrails (rate limiting, token budgets, log scrubbing).

## Decision

- Default LLM provider is `Fake` for deterministic tests and offline dev. Hugging Face provider is available when `CKA_LLM_PROVIDER=HF` and `HF_API_KEY` is set.
- API key authentication is supported via `CKA_API_KEY` header `X-CKA-API-Key` for simple protection. For production, prefer upstream gateway/OIDC.
- Security headers: always set X-Content-Type-Options, X-Frame-Options, Referrer-Policy; enable HSTS and CSP only when `CKA_HTTPS_ENABLED=true`.
- Rate limiting is keyed (API key or session) with consistent 429 and `Retry-After` header.
- Logs use structlog JSON; add scrubber processor to redact secrets/tokens, and include trace context when tracing is enabled.
- /version endpoint exposes `app_version`, `git_sha`, and `build_time` from build-time injection (`make version`).

## Consequences

- Tests are reliable and do not require network (Fake provider by default). E2E tests for external providers are marked and skipped when credentials are absent.
- Security can be tightened by toggling env flags in production without code changes.
- Build metadata is embedded and exposed for release traceability.

## Alternatives considered

- Enforcing HF provider by default: rejected due to flakiness and secret handling in CI.
- Always-on CSP/HSTS: rejected to avoid local dev friction and misconfiguration behind non-HTTPS proxies.
- JWT/OIDC within the service: deferred; recommended at the ingress/gateway level.
