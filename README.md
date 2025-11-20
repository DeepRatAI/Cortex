# Cortex Knowledge Assistant (RAG)

This repository contains a corporate-grade Retrieval-Augmented Generation (RAG) system designed for internal documentation assistance in enterprises. Employees can search, summarize, and ask questions about organization documents (manuals, policies, technical reports, procedures).

Although the example profile in this repository is a synthetic **corporate banking** assistant, the backend itself is domain-agnostic and can be reused across other corporate contexts (insurance, telco, retail, internal IT, etc.) by changing the corpus and configuration.

Disclaimer: This project is a synthetic, educational replica created for research and learning purposes. It is not affiliated with or representative of any real company or client.

> Project status: **production-ready backend (ships with synthetic scenario)**
>
> This repository contains a hardened backend and supporting scripts for a synthetic
> banking RAG assistant. The bundled scenario and data are synthetic for safety,
> but the backend is designed to be wired to your own corporate data sources and
> used in real-world enterprise environments.

## Who is this for?

This repository is aimed at teams who need more than a toy chatbot:

- **Banks and financial institutions** that want a **safe RAG backend** over internal policies, procedures, and product documentation.
- **Risk, Compliance, and Legal teams** that need **DLP-aware assistants** handling sensitive PII (national IDs, card numbers, account identifiers) in a controlled way.
- **Contact center and backoffice operations** that want a **copilot for agents**, grounded on official policies and auditable answers.
- **AI / Platform engineering teams** looking for a **production-ready RAG template** (FastAPI + Qdrant + Hugging Face + CI) instead of one-off notebooks or prototypes.

The goal is to provide a reusable backend, not a fixed "chatbot product": you can plug in your own corpus, auth, and identity layer while reusing the security and RAG building blocks.

## Real-world scenarios

### Customer service and backoffice agents (standard users)

- Ask questions about **loan policies, eligibility criteria, fees, and procedures** over a synthetic banking corpus.
- Get **grounded answers with citations**, showing exactly which policy documents and sections support each answer (`used_chunks`, `citations`).
- Rely on **DLP enforcement for standard users**: if an agent includes PII (e.g. DNI, card number) in the query, the backend prevents that PII from being echoed back in the answer.

This maps to the **standard demo user** (`dlp_level="standard"`), using the demo API key documented in this repo.

### Risk, Compliance, and audit teams (privileged users)

- Investigate **specific synthetic cases that contain PII** under a **privileged role** (e.g. backoffice risk manager, fraud analyst).
- Ask the assistant to summarize **risk signals, applicable controls, and next steps** for a suspicious transaction, while having backend-level control over when PII can appear in the answer.
- Use the structured response (`used_chunks`, `citations`) and logs to **explain and audit** why a particular recommendation was produced and which policies back it.

This corresponds to the **privileged demo user** (`dlp_level="privileged"`), which is only meant for tightly controlled lab environments and is intentionally out of scope for public GitHub Actions demos.

### AI / Platform teams (reusable template)

- Clone this project as a **reference implementation for internal RAG assistants**:
  - Replace the synthetic banking corpus with your own documents.
  - Swap API keys for your preferred identity mechanism (IAM, OAuth/JWT, internal SSO).
  - Keep the same multi-tenant, DLP, and logging architecture.
- Build on top of a **tested, CI-backed backend**:
  - Unit and integration tests (including DLP behaviour and prompt-safety tests).
  - GitHub Actions workflows for CI, SBOM generation, and image scanning.
  - End-to-end demos using a real HF provider and Qdrant.
- Use it as a **safe baseline** for environments with regulatory constraints (banking, insurance, public sector), instead of re-implementing RAG and DLP from scratch in every project.

## Why this project exists

> **Goal:** show that a **RAG backend with DLP and multi-tenant support** can be implemented in a way that is:
>
> - **Auditable** – answers are grounded on explicit chunks and citations, with structured logs and tracing metadata.
> - **Testable** – behaviour (including DLP and role-based differences) is covered by automated tests and reproducible E2E demos.
> - **Deployable in regulated environments** – DLP and user roles (`standard` vs `privileged`) are enforced in the backend, not just "prompted" in the UI.

It is meant to serve as a **reference backend** that banking and enterprise teams can fork and adapt:

- Keep the **security and observability model** (API key / IAM, `CurrentUser`, DLP, logging, tracing).
- Swap in your own corpus, tenants, and identity system.
- Extend the workflows and demo scripts (e.g. `docs/DEMO_FULL_E2E_REAL.md`, `scripts/demo_full_e2e_real.py`, `scripts/demo_roles_banking.py`) to showcase your own real-world scenarios.

## Table of contents

- [Objectives](#objectives)
- [High-level Architecture](#high-level-architecture)
- [Quick start (dev)](#quick-start-dev)
- [Quickstart (HF real mode)](#quickstart-hf-real-mode)
- [Switching providers](#switching-providers)
- [Troubleshooting 401/429/Timeout](#troubleshooting-401429timeout)
- [Developer workflow](#developer-workflow)
- [Features of interest](#features-of-interest)

  - [DLP and PII redaction](#dlp-and-pii-redaction)
  - [Admin CLI](#admin-cli)
  - [Observability and SIEM (summary)](#observability-and-siem-summary)

- [Architecture and security](#architecture-and-security)

  - [Modes of operation: demo vs real](#modes-of-operation-demo-vs-real)
  - [Secrets and configuration management](#secrets-and-configuration-management)
  - [Secure deployment best practices](#secure-deployment-best-practices)
  - [Banking pre-production checklist](#banking-pre-production-checklist)

- [Security model (overview)](#security-model-overview)
- [Try it quickly](#try-it-quickly)
- [Compliance & Supply Chain](#compliance--supply-chain)
- [License](#license)

## Objectives

- Private, on-prem friendly RAG stack
- Clean architecture (layered/hexagonal) with strong typing and docs
- Production-ready DevEx: lint, type-check, tests, CI, Docker, Compose

## High-level Architecture

- Presentation (FastAPI): REST endpoints for chat/search.
- Application layer: orchestrates retrieval + generation (RAGService, DLP, rate limiting).
- Domain: core models and contracts (ports) for retrievers, LLMs, storage, and security.
- Infrastructure: adapters for embeddings (SentenceTransformers), vector DB (Qdrant),
  HTTP client for the LLM provider, and optional cache backends.

Default runtime components:

- API service: FastAPI app (`cortex_ka.api.main:app`).
- Qdrant (optional): vector store used when `CKA_USE_QDRANT=true`.
- LLM provider: Fake (in tests) or Hugging Face router (`CKA_LLM_PROVIDER=HF`).

Optional / future components (not required for the basic flow described here):

- Redis or similar cache for RAG caching.

## Quick start (dev)

1. Create and activate a virtualenv, then install dependencies:

```bash
cd new
python3 -m venv .venv
source .venv/bin/activate
make install
```

2. Create `.env` from template (or from the examples in this README) and
   configure at least `CKA_LLM_PROVIDER`, `CKA_API_KEY` and, if using HF,
   `HF_API_KEY`.

3. Run the API locally:

```bash
make run
```

4. Open API docs:

- [http://localhost:8088/docs](http://localhost:8088/docs)

## Quickstart (HF real mode)

Run with Hugging Face provider — needs a valid `HF_API_KEY` (never commit):

1. Ensure the virtualenv is active and dependencies are installed (`make install`).

2. Edit `.env` and set:

- `CKA_LLM_PROVIDER=HF`
- `HF_API_KEY=<your real HF token>`
- Optional: `CKA_HF_MODEL=<model name>`

3. Start the API as before:

```bash
make run
```

4. Sanity checks via curl (expect `provider="hf"` and `provider_ok=true` once model loaded; `hint` may appear while loading):

```bash
# Health (provider should be hf and provider_ok true)
curl -s http://localhost:8088/health | jq

# Version (build metadata)
curl -s http://localhost:8088/version | jq

# Query (add API key header if you set CKA_API_KEY)
curl -s -X POST http://localhost:8088/query \
	-H 'Content-Type: application/json' \
	-H "X-CKA-API-Key: ${CKA_API_KEY:-}" \
	-d '{"query":"What is our incident process?"}' | jq

# Streaming (enable first: CKA_ENABLE_STREAMING=true)
curl -s http://localhost:8088/chat/stream?q=hello
```

Notes:

- If you configured `CKA_API_KEY`, include header `X-CKA-API-Key: <value>` in requests.
- Streaming endpoint returns Server-Sent Events (lines starting with `data:`).

For local experimentation with the bundled demo users:

- Standard demo user (DLP redaction applied):

  ```bash
  export CKA_API_KEY=demo-key-cli-81093
  curl -s -X POST http://localhost:8088/query \
    -H 'Content-Type: application/json' \
    -H "X-CKA-API-Key: ${CKA_API_KEY}" \
    -d '{"query":"My DNI is 12.345.678"}' | jq
  ```

- Privileged demo user (bypass DLP, only for lab/backoffice scenarios):

  ```bash
  export CKA_API_KEY=demo-key-cli-81093-ops
  curl -s -X POST http://localhost:8088/query \
    -H 'Content-Type: application/json' \
    -H "X-CKA-API-Key: ${CKA_API_KEY}" \
    -d '{"query":"My DNI is 12.345.678"}' | jq
  ```

In real environments, replace these demo keys with your own identity provider
and derive `CurrentUser.allowed_subject_ids` + `CurrentUser.dlp_level` from
JWT/OIDC claims or your IAM system.

## Switching providers

- Fake (default): no external calls, deterministic tests. Set `CKA_LLM_PROVIDER=Fake` (or unset).
- Hugging Face: set `CKA_LLM_PROVIDER=HF` and provide `HF_API_KEY`. Useful for “real” responses.

Switching is hot-configurable via env and service restart; no code changes required.

## Troubleshooting 401/429/Timeout

- 401 Unauthorized

  - Ensure the `X-CKA-API-Key` header matches `CKA_API_KEY` (if configured).
  - Verify your reverse proxy doesn’t strip custom headers.

- 429 Rate limited

  - Requests/min per key is controlled by `CKA_RATE_LIMIT_QPM` (and `CKA_RATE_LIMIT_BURST`).
  - Check the `Retry-After` response header for backoff.
  - For distributed deployments, prefer gateway-level rate limiting.

- Timeouts / slow responses

  - Confirm upstream provider (HF) status and network egress.
  - Reduce retrieval `CKA_QDRANT_TOP_K` and/or enable `CKA_USE_REDIS=true` for caching.
  - Inspect `/metrics` histograms for latency hotspots.

## Developer workflow

```bash
make install         # install deps
make lint            # flake8 + pylint
make format          # black + isort
make typecheck       # mypy
make test            # pytest (see below for local slow/e2e guidance)
make audit           # pip-audit
make version         # embed git sha + build time into build_info.py
make sbom            # generate CycloneDX SBOM with Syft (sbom.json)
make scan            # build and scan image with Trivy (fail on HIGH/CRITICAL)
make e2e             # run end-to-end tests (may be skipped without creds)
make smoke           # run local smoke script against running API
```

Pytest quick reference:

- Fast local runs (without tests marked as `slow`):

  ```bash
  pytest -m "not slow"
  ```

- Fast suite used in CI (excludes slow and some heavy e2e): check the
  GitHub Actions workflow in `.github/workflows/` to see the exact configuration.

## Documentation

- `RUNBOOK.md` — operational runbook for the synthetic banking demo (Qdrant + corpus + API).
- `docs/DEMO_FULL_E2E_REAL.md` — description of the GitHub Actions E2E demos (v1/v2).

Additional architecture and security notes are embedded in this README and in code
docstrings. New documents (architecture, ADRs, security deep-dives) can be added
incrementally as the project evolves.

## Features of interest

- Security headers with optional CSP/HSTS when `CKA_HTTPS_ENABLED=true`.
- /version endpoint publishes app_version, git_sha, and build_time for traceability.
- LLM provider selection via `CKA_LLM_PROVIDER` (Fake default; `HF` with `HF_API_KEY`).
- Streaming SSE endpoint `/chat/stream` gated by `CKA_ENABLE_STREAMING`.

### DLP and PII redaction

- The API applies PII redaction in the application layer right before returning the response.
- The entry point is the `enforce_dlp()` function in `src/cortex_ka/application/dlp.py`, which currently delegates to `redact_pii()`.
- The `CKA_DLP_ENABLED` flag allows enabling/disabling DLP enforcement (enabled by default).
- The user context (`CurrentUser`) includes a DLP level (`dlp_level`) that allows modeling different profiles:

  - `standard`: default level; responses are returned with PII redacted.
  - `privileged`: intended for operators in strongly controlled environments; they can see responses without additional redaction as long as global DLP is enabled.

- This design allows you to swap the redaction engine for a stricter corporate DLP in the future without changing endpoints, and to map levels (`dlp_level`) to real IAM roles or groups.

### Admin CLI

In `scripts/cka_admin.py` there is a small CLI intended for operations and quick tests:

- `python scripts/cka_admin.py health` — performs a GET to `/health` and shows the JSON.
- `python scripts/cka_admin.py check-config` — prints a summary of critical variables (without exposing complete secrets).
- `python scripts/cka_admin.py test-dlp "test text with DNI 12.345.678"` — applies the same redaction logic as the API and shows original vs redacted.

It is useful for smoke tests from bastions or CI, and to verify that DLP/PII configuration is working as expected.

### Observability and SIEM (summary)

- Structured logs with `structlog` include `request_id`, `user_id`, `subject_id`, endpoint and status codes.
- These logs are designed to be sent to a central aggregator (ELK, Loki, Azure Monitor, etc.) and from there to a SIEM for correlation and alerts.
- The `/metrics` endpoint exposes Prometheus metrics (latencies, error counters, etc.) for dashboards and alerts.
- Optional OpenTelemetry integration allows tracing each request end-to-end without exposing PII in spans or attributes.

## Architecture and security

### High-level view

The full flow of a query in this multi-tenant RAG system is:

```text
Client (browser / frontend / tool)
    |
    |  HTTPS + security headers
    v
Reverse proxy / API Gateway (Nginx, APIM, Kong, Istio, ...)
    |
    |  X-CKA-API-Key / (future: JWT/OIDC)
    v
FastAPI (cortex-ka API)
    |
    |-- AuthN/AuthZ -> get_current_user()  ─────────────┐
    |       (API key -> CurrentUser(user_id,            |
    |                   allowed_subject_ids[id_cliente]))|
    v                                                   |
RAGService (application)                                |
    |
    |  subject_id = CurrentUser.allowed_subject_ids[0]  |
    v                                                   |
QdrantRetriever (infra)                                |
    |
    |  filter: metadata.info_personal.id_cliente == subject_id
    v
Qdrant (vector DB)
    |
    |  relevant chunks
    v
LLM (Fake / Hugging Face Router)
    |
    |  raw response (may contain PII)
    v
redact_pii() (redaction layer)
    |
    |  response without sensitive PII
    v
HTTP Response (/query or /chat/stream)
```

Key points:

- **Real multi-tenant**: the `subject_id` used to filter in Qdrant NEVER comes
  from client headers or body; it is always derived from `CurrentUser`.
- **Tenant-aware cache**: the cache key in `RAGService` includes `subject_id`
  and `query` to avoid mixing responses between clients.
- **PII redaction**: applied right before returning the response to the client, so
  the model can reason with full context but the output channel complies with
  banking-grade expectations.
- **Security headers**: middleware adds `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy` always, and `Strict-Transport-Security` + `Content-Security-Policy` when
  `CKA_HTTPS_ENABLED=true`.

### Modes of operation: demo vs real

#### Demo mode (local development / PoC)

Designed for laptops or lab environments without real data:

- LLM:

  - `CKA_LLM_PROVIDER=Fake` or `HF` with a small model.
  - `HF_API_KEY` can be a test token (never a production token).

- Qdrant:

  - You can disable Qdrant and use the stub retriever:

    - `CKA_USE_QDRANT=false` (default in many tests).

  - Or point to a local Qdrant in Docker:

    - `CKA_USE_QDRANT=true`
    - `CKA_QDRANT_URL=http://localhost:6333`

- Auth:

  - Enable the demo API key to have simple multi-tenant behavior:

    - `CKA_API_KEY=demo-key-cli-81093`

  - This value is mapped in `_DEMO_USER_MAP` to a `CurrentUser` representing
    a synthetic customer (`CLI-81093`) with `dlp_level="standard"`.
  - For advanced tests or backoffice demo there is an additional API key mapped to
    a user with `dlp_level="privileged"`; in real environments you should replace it
    with a specific role/claim in your IAM and only use it in controlled networks/environments.

- Streaming:

  - Normally disabled:

    - `CKA_ENABLE_STREAMING=false`

  - Enable only in trusted networks:

    - `CKA_ENABLE_STREAMING=true` to use `/chat/stream`.

#### Real mode (pre-production / production)

Recommended when handling sensitive information or real customers:

- **Secure environment**

  - Place the API behind a reverse proxy with TLS (e.g. `https://cka.bank.corp`).
  - Set `CKA_HTTPS_ENABLED=true` to enable HSTS + CSP.
  - Review `CKA_CORS_ORIGINS` to limit legitimate origins (e.g. `https://intranet.bank.corp`).

- **Auth & tenants**

  - Use real API keys managed by IAM or, ideally, JWT/OIDC:

    - `CKA_API_KEY` can act as an additional “guard rail” in the gateway.
    - Replace `_DEMO_USER_MAP` with a real identity resolver:

      - A `Depends` that decodes a JWT (e.g. header `Authorization: Bearer ...`).
      - Extract `allowed_subject_ids` from claims (`sub`, `tenant_id`, `customer_ids`).

  - Golden rule: `subject_id` must come **only** from attributes/claims of the authenticated user.

- **Qdrant and data**

  - Keep `CKA_USE_QDRANT=true` and point to a dedicated service:

    - `CKA_QDRANT_URL=http://qdrant:6333` or a secure internal URL.

  - If Qdrant requires API key, configure it via `CKA_QDRANT_API_KEY` and never commit it.

- **LLM**

  - Use `CKA_LLM_PROVIDER=HF` pointing to a commercially backed model.
  - Inject `HF_API_KEY` via platform secrets (Kubernetes Secrets, Vault,
    Key Vault, etc.).
  - Define `CKA_HF_MODEL` explicitly to facilitate model governance.

### Secrets and configuration management

This repo includes a very commented `.env.example` as reference. Important rules:

- **Never** commit `.env` with real values:

  - Add `.env` to `.gitignore` (already included) and manage real values
    via secrets in CI/CD or vault tools.

- Always treat the following fields as secrets:

  - `HF_API_KEY`
  - `CKA_API_KEY` (when real)
  - `CKA_QDRANT_API_KEY`
  - Any token, password or URL with embedded credentials.

- For multi-team environments, use `.env.example` only as a key catalog
  and document in this README where real secrets are stored (for
  example: “Azure Key Vault: kv-cka-prod”, “HashiCorp Vault path: kv/cka”).

For a more detailed configuration matrix between **lab mode** and
**banking/production mode**, see the
“Configuration profiles: Lab vs Banking” section in `docs/security.md`.

### Secure deployment best practices

- **End-to-end TLS**: always expose the API behind HTTPS. If TLS is terminated at a
  gateway, also protect the internal hop with mTLS or a private network.
- **Key rotation**: plan periodic rotation of `HF_API_KEY` and
  `CKA_API_KEY` (if used) and automate the deployment of new secrets.
- **OIDC/JWT**: integrate an identity provider (Azure AD, Keycloak, Auth0)
  to issue tokens that include the allowed `id_cliente` values and re-implement
  `get_current_user` to derive `CurrentUser` from those tokens.
- **Principle of least privilege**: Qdrant and Redis should be in internal networks
  and only accessible from necessary services.
- **Observability and auditing**:

  - Use structured logs and `X-Request-ID` to trace requests.
  - Avoid logging full prompt/response content in production; if
    needed, anonymize or pseudonymize first.

### Banking pre-production checklist

Before exposing the assistant in a banking/real environment, verify at least:

- **API key and auth**

  - Do not use the demo API key (`demo-key-cli-81093`).
  - `CKA_API_KEY` managed via secret store / gateway (or replaced by JWT/OIDC in `get_current_user`).

- **DLP and PII**

  - `CKA_DLP_ENABLED=true` in all pods/services.
  - Check that DLP tests (CLI `cka_admin.py test-dlp` and tests) pass in the target environment.
  - Ensure only very restricted backoffice accounts/roles use profiles with
    `dlp_level="privileged"` (end users must operate with `dlp_level="standard"`).

- **Streaming**

  - `CKA_ENABLE_STREAMING=false` by default.
  - Only enable `/chat/stream` in trusted networks and with proper monitoring.

- **RAG and Qdrant**

  - `CKA_USE_QDRANT=true` pointing to a managed Qdrant (not the stub).
  - `CKA_QDRANT_API_KEY` configured and Qdrant protected (not publicly exposed).

- **HTTPS / CORS**

  - API behind an ingress / proxy with proper TLS.
  - `CKA_HTTPS_ENABLED=true` when traffic arrives over HTTPS.
  - `CKA_CORS_ORIGINS` limited to authorized frontends and tools (not `*`).

- **Observability and secrets**

  - Logs and metrics (`/metrics`) integrated with the monitoring/SIEM stack.
  - `HF_API_KEY`, `CKA_API_KEY`, `CKA_QDRANT_API_KEY` and other secrets provided only via secret manager (not in committed `.env`).

## Security model (overview)

- Authentication & authorization

  - Requests are authenticated via `CKA_API_KEY` and bound to a `CurrentUser`
    context which carries:

    - `user_id`
    - `allowed_subject_ids` (list of allowed customer ids)
    - `dlp_level` (PII protection level for that user, e.g. `standard` or `privileged`).

  - The `/query` endpoint no longer trusts client-provided `subject_id`
    or `X-CKA-Subject-Id` headers; instead the effective `subject_id` used for
    retrieval is derived from `CurrentUser`. This prevents cross-tenant access
    via header manipulation.

- Multi-tenant retrieval

  - The Qdrant retriever always applies a filter on
    `metadata.info_personal.id_cliente == subject_id`, so each query is scoped
    to a single customer identifier. Tests exercise isolation between
    different `id_cliente` values.

- PII redaction

  - Before responses leave the backend, a lightweight redactor masks common
    PII patterns (DNI, CUIT/CUIL, card numbers, emails, phones) in the LLM
    output while keeping the answer semantically useful.

- Logging

  - Structured logs are produced via structlog with basic secret scrubbing.
    Application logs intentionally avoid dumping raw payloads or full metadata
    structures that may contain PII; instead they record request ids, user ids,
    and high-level events suitable for regulated environments (e.g. banking).

## Try it quickly

Run a smoke check (expects API on localhost:8088):

```bash
make smoke
# or override base URL
# SMOKE_BASE_URL=http://localhost:8000 make smoke
```

Dev compose (minimal) example (`docker/docker-compose.dev.yml`):

```yaml
services:
  api:
    build:
  context: ../
      dockerfile: docker/Dockerfile.api
    env_file: ../.env
    ports:
      - "8000:8088"
    # Uncomment below to enable vector store & cache
    # depends_on:
    #   - qdrant
    #   - redis
  # qdrant:
  #   image: qdrant/qdrant:latest
  #   ports:
  #     - "6333:6333"
  # redis:
  #   image: redis:7-alpine
  #   ports:
  #     - "6379:6379"
```

Validate compose config:

```bash
docker compose -f docker/docker-compose.dev.yml config >/dev/null
```

## Compliance & Supply Chain

- SBOM: `make sbom` (requires Syft installed locally). CI uploads artifact.
- Image scanning: `make scan` (requires Trivy). CI fails on HIGH/CRITICAL issues.

## License

MIT — see LICENSE
