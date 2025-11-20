# Banking Deployment Profile

This document describes a reference deployment profile for running Cortex KA
in banking or similarly regulated environments. It builds on the existing
security model, DLP integration, and Kubernetes manifests already present in
this repository.

It is not a one-size-fits-all prescription; each institution should adapt
these recommendations to their own standards, controls, and risk appetite.

## 1. High-level goals

- Preserve the existing API contract and multi-tenant isolation model.
- Enforce DLP/PII redaction on all responses via `enforce_dlp()`.
- Restrict network access to internal dependencies (Qdrant, Redis).
- Manage secrets via the platform's secret manager (not via git-committed `.env`).
- Provide an auditable, reproducible set of manifests and configuration knobs.

## 2. Core configuration (env flags)

See also `docs/security.md` (section "Configuration profiles: Lab vs Banking").
For a banking/production deployment, the minimum baseline is:

- `CKA_API_KEY`: **required**, non-demo value, provisioned as a secret.
- `CKA_DLP_ENABLED=true`: DLP must be active.
- `CKA_ENABLE_STREAMING=false`: enable `/chat/stream` only if necessary and
  only on trusted internal networks.
- `CKA_USE_QDRANT=true`: always use the real Qdrant retriever, not the stub.
- `CKA_HTTPS_ENABLED=true`: the API must be served over HTTPS (directly or via
  an ingress controller).
- `CKA_CORS_ORIGINS`: restricted to trusted frontends/tools (no `*`).
- `CKA_LLM_PROVIDER=HF` (or equivalent corporate provider) with `HF_API_KEY`
  supplied as a secret.
- `CKA_QDRANT_URL=http://cka-qdrant:6333` and `CKA_QDRANT_API_KEY` set as a
  secret if Qdrant authentication is enabled.

## 3. Kubernetes deployment layout

This repository ships with a minimal but opinionated set of Kubernetes
manifests under `k8s/`:

- `k8s/api/deployment.yaml`: Deployment for the API (`cka-api`).
- `k8s/api/service.yaml`: ClusterIP Service exposing the API on port 80.
- `k8s/api/configmap.yaml`: ConfigMap with non-secret environment variables.
- `k8s/api/secret-example.yaml`: Example Secret with API and HF/Qdrant keys.
- `k8s/qdrant/deployment.yaml`: Deployment for Qdrant (`cka-qdrant`).
- `k8s/qdrant/service.yaml`: Service for Qdrant (if present).
- `k8s/redis/deployment.yaml`: Deployment for Redis (`cka-redis`).
- `k8s/redis/service.yaml`: Service for Redis (if present).
- `k8s/networkpolicies/cka-api-egress.yaml`: NetworkPolicy restricting egress
  from the API pods to Qdrant and Redis only.

### 3.1 API Deployment

Key characteristics of `k8s/api/deployment.yaml`:

- `replicas: 3` (can be adjusted based on capacity needs).
- Probes against `/health` for both readiness and liveness.
- Environment configuration via:
  - `envFrom` ConfigMap `cka-api-config` (non-secrets), and
  - `envFrom` Secret `cka-secrets` (secrets).
- Resource requests/limits set to conservative defaults (adjust per SRE sizing).

In a typical banking deployment:

- Place the API in a dedicated namespace (e.g. `namespace: cka`).
- Front the Service `cka-api` with an Ingress or API Gateway that terminates
  TLS and enforces additional controls (WAF, rate limiting, auth).

### 3.2 Qdrant & Redis

- Run Qdrant (`cka-qdrant`) and Redis (`cka-redis`) in the same namespace but
  **never** expose them publicly.
- Use PersistentVolumeClaims instead of `emptyDir` for Qdrant storage in
  production, with appropriate backup/retention policies.
- If Qdrant authentication is enabled, set `CKA_QDRANT_API_KEY` in the
  `cka-secrets` Secret and configure Qdrant accordingly.

## 4. Network segmentation

Network policies are critical in regulated environments to reduce blast
radius.

The example `k8s/networkpolicies/cka-api-egress.yaml` implements:

- Default egress restrictions for pods labeled `app: cka-api`.
- Allow egress **only** to:
  - Pods labeled `app: cka-qdrant` on TCP port 6333, and
  - Pods labeled `app: cka-redis` on TCP port 6379.

Recommended enhancements for a full banking deployment:

- Add a default deny-all NetworkPolicy for the namespace.
- Add NetworkPolicies for ingress, limiting which pods or components can
  reach `cka-api`.
- If an Ingress controller is used, bound its access via label selectors.

## 5. Secrets management

The example `k8s/api/secret-example.yaml` is **not** meant for production as
is; it serves only as a template. For banking deployments:

- Store all sensitive values in the platform's secret manager (e.g. Azure Key
  Vault, HashiCorp Vault, AWS Secrets Manager, GCP Secret Manager) and inject
  them into Kubernetes Secrets via CI/CD.
- Secrets that must never be committed to git include:
  - `CKA_API_KEY` (real API keys).
  - `HF_API_KEY` (LLM provider tokens).
  - `CKA_QDRANT_API_KEY` (vector store auth).
- Align secret naming and rotation policy with internal standards; use
  short-lived tokens where possible.

## 6. Pre-production banking checklist

This expands on the checklist in `README.md` with a deployment-specific view.

Before routing real banking traffic to a Cortex KA deployment, verify at least:

1. **Configuration & secrets**

   - `CKA_API_KEY` is **not** the demo key and is provisioned from a secret
     manager.
   - `CKA_DLP_ENABLED=true` in all pods.
   - `CKA_ENABLE_STREAMING=false` unless a specific, approved use case and
     network segment exist.
   - `CKA_USE_QDRANT=true` and `CKA_QDRANT_URL` points to the managed Qdrant
     Service (not localhost).
   - All secrets (`HF_API_KEY`, `CKA_API_KEY`, `CKA_QDRANT_API_KEY`, etc.) are
     set via Kubernetes Secrets, not via ConfigMaps or `.env` files.

2. **Network & exposure**

   - The API is reachable only via HTTPS (Ingress/controller or API Gateway).
   - Qdrant and Redis are not exposed outside the cluster/namespace.
   - NetworkPolicies are in place to restrict egress from `cka-api` to only
     Qdrant and Redis.

3. **DLP & PII controls**

   - `CKA_DLP_ENABLED=true` and the DLP tests pass (see CLI below).
   - Unit and endpoint tests for PII redaction (`pytest`) have been run in
     the build pipeline.

4. **Observability & logging**

   - Logs from the API are ingested into the central logging/SIEM platform,
     with fields such as `request_id`, `user_id`, `subject_id`, endpoint name
     and status code.
   - `/metrics` is scraped by Prometheus (or equivalent) and has alerts for
     high error rate, elevated latency, and abnormal patterns in DLP/redaction
     metrics if available.

5. **Change management & rollback**
   - The LLM model configuration (`CKA_LLM_PROVIDER`, `CKA_HF_MODEL`) is
     recorded in a model registry or change ticket.
   - A rollback procedure exists (e.g. reverting `CKA_HF_MODEL` and redeploying
     the previous version) and has been tested in non-production.

## 7. Security smoke tests (using the admin CLI)

The CLI `scripts/cka_admin.py` can be used as a lightweight operational tool
in banking environments. Typical pre-go-live checks:

1. Health check:

   ```bash
   python scripts/cka_admin.py health --base-url https://cka.your-bank.corp
   ```

   - Expect HTTP 200 and a JSON payload from `/health`.

2. Configuration summary:

   ```bash
   python scripts/cka_admin.py check-config
   ```

   - Verify that all critical flags are set as expected (secrets shown only
     as `<set>` / `<unset>`).

3. DLP/PII redaction test:

   ```bash
   python scripts/cka_admin.py test-dlp "Mi DNI es 24567579 y mi tarjeta es 4915600297200043"
   ```

   - Confirm that the output masks the sensitive fields (DNI, card number,
     etc.) according to your policies.

These checks should be integrated into CI/CD or pre-production runbooks rather
than being executed only ad-hoc.

---

Update this document together with any changes to the Kubernetes manifests,
DLP configuration, or production deployment standards.
