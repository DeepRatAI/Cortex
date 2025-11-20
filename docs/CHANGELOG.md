# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project adheres to Semantic Versioning.

## [0.1.0] - 2025-11-09

### Added

- Initial corporate-grade scaffold with API, clean architecture, tests, CI config, and Docker Compose.

## [0.1.1] - 2025-11-09

### Added

- Prometheus metrics (/metrics) with counters & histograms.
- Citations in query responses.
- Health endpoint.
- Evaluation script for latency.

## [0.1.2] - 2025-11-09

### Added

- Security headers middleware.
- Reverse engineering report & Mermaid diagrams.
- Requirements lock-style plain files (requirements\*.txt) for reproducibility.

### Changed

- Makefile run target path corrected.

## [0.1.3] - 2025-11-09

### Added

- OpenTelemetry tracing (optional via CKA_ENABLE_TRACING).
- Redis cache selectable via CKA_USE_REDIS with graceful fallback.
- Token budget guard (approx and tiktoken-enabled when installed).

## [0.1.4] - 2025-11-10

### Added

- /version endpoint exposing git SHA and build time (build metadata injection via `make version`).
- Hugging Face LLM provider abstraction selectable by `CKA_LLM_PROVIDER=HF`.
- Log scrubbing processor to redact tokens/secrets.
- Keyed rate limiting with consistent 429 + Retry-After.
- SSE streaming endpoint `/chat/stream` gated by `CKA_ENABLE_STREAMING`.
- ADR 0005 defining security and provider strategy.

### Changed

- Security headers expanded (conditional CSP/HSTS behind `CKA_HTTPS_ENABLED`).
- Health endpoint reports provider and health status.

## [0.1.5] - 2025-11-10

### Added

- Makefile targets: `version`, `sbom`, `scan`, `e2e`.
- SBOM generation (Syft) and image scanning (Trivy) integrated into CI (fail on HIGH/CRITICAL).
- Streaming and HF provider end-to-end tests with conditional skips.

### Documentation

- Updated security & compliance docs with SBOM/image scanning procedures.

## [0.1.6] - 2025-11-10

### Documentation / DX

- Comprehensive `.env.example` with annotated variables (HTTPS/CSP, provider, streaming, rate limits, token budgets, logging, Qdrant/Redis).
- README additions: real-mode quickstart, provider switching, troubleshooting 401/429/timeout, curl examples.
- Runbook expanded: operational toggles, detailed incident playbooks, rollback, ambiguous default rationale.
- ADR-0005 cross-referenced indirectly via README and runbook.
- Lint housekeeping (ignored W391) without functional changes.

### Note

- No runtime behavior or defaults changed in this release (documentation & DX only).
