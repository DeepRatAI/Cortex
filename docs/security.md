# Security Policy & Governance

This system applies a baseline of security controls inspired by:

- **OWASP ASVS** (Application Security Verification Standard)
- **OWASP Top 10**
- **OWASP Top 10 for LLM Applications** (emerging guidance)

The implementation here does not claim full certification against these
standards. Instead, it provides traceability and structure so that a security
team can map individual controls to OWASP requirements and extend them.

## HTTPS Mode (CKA_HTTPS_ENABLED=true)

**OWASP ASVS mapping (partial):**

- ASVS 2.x / 3.x (Transport Layer Security)
- ASVS 14.x (Configuration) for strict header management

When HTTPS mode is enabled:

- Strict-Transport-Security: `max-age=63072000; includeSubDomains; preload`
- Content-Security-Policy: configurable via `CKA_CSP_POLICY` (default is strict self-based policy)

### CSP Examples

- Default:
  - `default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'`
- With external CDN (report-only):
  - Set header `Content-Security-Policy-Report-Only` with policy allowing the CDN and set `report-uri` to your collector.
- Nonce-based approach:
  - Generate a per-request nonce and include `'nonce-<value>'` in `script-src` and inlined scripts; requires middleware to inject the nonce into templates.

## Report-Only Mode

- For gradual rollout, apply `Content-Security-Policy-Report-Only` instead of `Content-Security-Policy`. Inspect reports, then enforce.

## Authentication & Multi-tenancy

**OWASP ASVS mapping (partial):**

- ASVS 2.x (Authentication)
- ASVS 4.x (Access Control)

The current implementation uses API key authentication (`CKA_API_KEY`) and a
`CurrentUser` context with `allowed_subject_ids` to enforce tenant isolation
(`id_cliente`). In production, replace the demo API key mapping with a
gateway- or IdP-backed JWT/OIDC flow that provides the same information via
claims.

## Version endpoint

- `/version` exposes `app_version`, `git_sha`, and `build_time`. Populate via `make version` in build pipelines to ensure traceability.

## PII, LLM Risks & Secrets

**OWASP Top 10 for LLM mapping (partial):**

- Prompt Injection (LLM01): mitigated partially by server-side retrieval
  and not exposing raw system prompts to callers.
- Data Leakage (LLM02): addressed via tenant-scoped retrieval in Qdrant and
  the `redact_pii` layer, with a dedicated DLP facade ready for stricter
  enforcement.
- Inadequate Sandboxing (LLM05): the LLM does not execute code or issue
  direct system commands; integration points are deliberately narrow.

PII & secrets handling:

- Avoid logging raw inputs. A scrubber removes tokens/PII patterns when logging.
- `redact_pii` is applied before responses are returned to clients.
- Secrets such as `HF_API_KEY`, `CKA_API_KEY`, and `CKA_QDRANT_API_KEY` are
  never hard-coded and should be supplied via secret stores in real deployments.

For stricter Data Loss Prevention, see `src/cortex_ka/application/dlp.py`, which
exposes a generic `enforce_dlp` facade controlled by `CKA_DLP_ENABLED`.

## Configuration profiles: Lab vs Banking

The same codebase can run in a lightweight "lab" mode (PoC, laptops) or in a
more locked-down "banking" mode. The following table summarises recommended
values for key environment flags; concrete deployments should adapt them to
their own standards and risk appetite.

| Flag                   | Lab / PoC (local)                                                         | Banking / Production (recommended)                                                       | Rationale                                                                                       |
| ---------------------- | ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `CKA_API_KEY`          | Optional; demo key (`demo-key-cli-81093`) acceptable only in isolated dev | **Required**, managed via secret store / gateway; never use demo key                     | AuthN / access control; API keys must be unique per client and rotateable.                      |
| `CKA_DLP_ENABLED`      | `true` (default); may be set to `false` in controlled tests               | **Always `true`**                                                                        | Ensures `enforce_dlp()` is active so that PII/redaction policies are enforced on all responses. |
| `CKA_ENABLE_STREAMING` | `true` or `false` depending on need                                       | `false` by default; enable only on trusted internal networks or channels                 | Streaming complicates monitoring and can increase exfiltration surface; better opt-in.          |
| `CKA_USE_QDRANT`       | `false` allowed (stub retriever)                                          | `true` (real Qdrant enforced)                                                            | Ensures RAG uses the governed, audited vector store rather than an in-memory stub.              |
| `CKA_HTTPS_ENABLED`    | `false` when running behind plain HTTP on localhost                       | `true` when served over HTTPS or behind an HTTPS ingress                                 | Activates HSTS and CSP headers; only safe when TLS is present end-to-end or at ingress.         |
| `CKA_CORS_ORIGINS`     | `*` acceptable for isolated dev                                           | Restricted to trusted origins (web frontends, tools)                                     | Limits which browser origins can call the API, reducing XSRF/abuse risks.                       |
| `CKA_LOG_LEVEL`        | `DEBUG`/`INFO`                                                            | `INFO`/`WARNING` (avoid `DEBUG` in production)                                           | Prevents noisy logs and reduces the risk of accidentally logging sensitive context.             |
| `CKA_ENABLE_TRACING`   | `false` or `true` pointing to a local collector                           | `true` pointing to a central OTEL collector; no PII in spans                             | Enables end-to-end observability; span attributes must be scrubbed of PII/secret material.      |
| `HF_API_KEY` / secrets | Test tokens acceptable; stored in `.env` for convenience                  | Provisioned via secret manager (Vault, KMS, Key Vault, etc.), **never** in `.env` or git | Secrets management must comply with internal policies and audit requirements.                   |
| `CKA_QDRANT_API_KEY`   | Often empty in local Docker setups                                        | Set and managed as a secret; Qdrant configured to require auth                           | Prevents unauthorised access to the vector store, which may contain sensitive embeddings.       |

## Model lifecycle (onboarding, evaluation, rollback)

In regulated environments (e.g. banking), LLM and embedding models must follow
a controlled lifecycle, similar to other critical components.

### 1. Onboarding

- Create a model record in your internal registry with:
  - Provider (e.g. Hugging Face Router)
  - Model id (e.g. `meta-llama/Llama-3.1-8B-Instruct`)
  - Version / commit hash or date
  - Intended use cases and risk classification
- Configure `CKA_LLM_PROVIDER` and `CKA_HF_MODEL` accordingly in a non-prod
  environment.
- Ensure secrets (HF tokens, etc.) are provisioned via the platform's
  secret manager.

### 2. Evaluation

- Run automated tests:
  - Unit/integration tests (pytest) – already part of this repo.
  - Regression sets of Q&A pairs representative of your domain (policies,
    procedures, compliance rules).
- Add evaluation scripts (outside of this core) to score:
  - Factual accuracy
  - Hallucination rate
  - Compliance with style/policy guidelines
  - PII leakage under adversarial prompts
- Store evaluation reports in a central system (e.g. model registry).

### 3. Approval & rollout

- Require sign-off from:
  - Business owner
  - Security/Compliance
  - Data Protection / Privacy
- Update the deployment configuration (Kubernetes ConfigMap / Helm values) to
  point production to the approved model id.
- Roll out gradually (canary or blue/green) by routing a subset of traffic to
  the new model while monitoring metrics and logs.

### 4. Monitoring & drift

- Continuously monitor:
  - Error rates and latency (Prometheus metrics)
  - Security signals (e.g. number of PII redactions, blocked prompts)
  - User feedback / rating systems where applicable
- Periodically re-run evaluation suites to detect performance or behaviour
  drift.

### 5. Rollback

- Always keep the previous model configuration ready-to-redeploy.
- In case of incidents (e.g. unexpected leakage, policy breach), restore the
  prior model by reverting configuration (e.g. `CKA_HF_MODEL`) and redeploying.
- Document the incident and its remediation as part of your change management
  and risk processes.

---

Update this document alongside any changes to auth, header policy, DLP
behaviour, or model lifecycle.
