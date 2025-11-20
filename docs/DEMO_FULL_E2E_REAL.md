# Full E2E Real Demo – Cortex Knowledge Assistant

This document describes how to run a full end-to-end demo of Cortex
Knowledge Assistant using a **real HF provider**, **RAG logic** (stub
or Qdrant, depending on environment), **DLP**, and the public HTTP API.

The demo is designed primarily to run in **GitHub Actions** as a
manual workflow, using a real `HF_API_KEY` stored as a secret.

## Overview

The demo performs the following steps:

1. Starts the FastAPI application (Cortex KA API) in the CI runner.
2. Uses the `HFLLM` provider (Hugging Face Inference API) with
   `HF_API_KEY` provided via GitHub Secrets.
3. Calls `/health` to ensure:
   - `provider == "hf"`
   - `provider_ok == true`
4. Calls `/query` three times:
   - A normal banking-style question.
   - A question about confidentiality policies.
   - A question containing explicit PII (DNI + card number) to
     validate **DLP**.
5. Prints the full JSON responses to stdout and asserts that:
   - PII patterns do **not** appear literally in the `answer`.
   - The response structure contains `used_chunks` and `citations`.

If any invariant fails (wrong provider, provider not healthy, PII leak,
missing structural fields), the script exits with non-zero status,
causing the workflow to fail.

On top of this v1 demo, there is a **v2 demo** that more closely
resembles a production-like deployment:

- Starts a real Qdrant service inside the GitHub Actions job.
- Ingests the full synthetic banking corpus
  (`corpus_bancario_completo.jsonl`) into Qdrant.
- Runs the API configured with `CKA_USE_QDRANT=true` so that `/query`
  uses **real RAG** against the corpus.
- Executes the same style of `/health` and `/query` checks, but with
  responses grounded on the ingested corpus.

### v1 vs v2 at a glance

| Demo | Workflow                                    | LLM provider |   Retriever | Corpus                           | Primary purpose                          |
| ---- | ------------------------------------------- | -----------: | ----------: | -------------------------------- | ---------------------------------------- |
| v1   | `.github/workflows/ci_full_e2e_demo.yml`    |           HF |        Stub | None                             | Smoke HF + DLP over the public API       |
| v2   | `.github/workflows/ci_full_e2e_demo_v2.yml` |           HF | Qdrant real | `corpus_bancario_completo.jsonl` | Production‑simulated RAG + HF + DLP demo |

Both demos use the same API contracts and the same demo script
(`scripts/demo_full_e2e_real.py`); the only differences are the
retriever wiring and whether a real corpus is present.

## Components

### 1. Demo script

- Path: `scripts/demo_full_e2e_real.py`
- Behavior:
  - Reads configuration from environment:
    - `CKA_DEMO_BASE_URL` (default: `http://localhost:8000` in local
      runs; in CI we use `http://127.0.0.1:8088`).
    - `CKA_API_KEY` (default: `demo-key-cli-81093`).
  - Performs an HTTP GET to `/health` and asserts:
    - `provider == "hf"`
    - `provider_ok == true`
  - Sends three HTTP POST requests to `/query` with header
    `X-CKA-API-Key` set to `CKA_API_KEY`.
  - Verifies that known PII fragments (DNI and card) are **not**
    present in the `answer` field.
  - Verifies that `used_chunks` and `citations` are present in the
    response payload.

The script does not mutate any state; it is only a consumer of the
public API. The variant is controlled via the `CKA_DEMO_VARIANT`
environment variable:

- `CKA_DEMO_VARIANT=v1` (default): HF provider + DLP, retriever
  configuration as provided by the environment (in CI v1 we typically
  use the stub retriever to simplify infra).
- `CKA_DEMO_VARIANT=v2`: HF provider + DLP + Qdrant real (RAG against
  the synthetic banking corpus). The behavior is driven by the
  workflow described below.

By default, the demo uses `CKA_API_KEY=demo-key-cli-81093`, which is
mapped to the **standard demo user** (`dlp_level="standard"`). For
this user, DLP redaction is always applied in the responses.

For lab-only backoffice experiments you may point `CKA_API_KEY` to the
**privileged demo key** (`demo-key-cli-81093-ops`), which is mapped to
`dlp_level="privileged"`. This is intentionally out of scope for the
GitHub Actions demo workflows and MUST only be used in tightly
controlled environments.

### 2. GitHub Actions workflow (v1)

- Path: `.github/workflows/ci_full_e2e_demo.yml`
- Trigger: `workflow_dispatch` (manual execution only).
- Jobs (single job: `demo-e2e`):
  - Sets up Python 3.12.
  - Installs the project:
    - `pip install -e .`
    - `pip install -r requirements-dev.txt`
  - Exposes environment variables:
    - `HF_API_KEY` from GitHub Secret (required for HF provider).
    - `CKA_LLM_PROVIDER=HF`.
    - `CKA_DLP_ENABLED=true`.
    - `CKA_USE_QDRANT=false` (demo uses stub retriever in CI to avoid
      infra overhead; Qdrant can be enabled in a future variant).
    - `CKA_FAKE_LLM=false`.
    - `CKA_API_KEY=demo-key-cli-81093`.
    - `CKA_DEMO_BASE_URL=http://127.0.0.1:8088`.
  - Starts the API server in background with uvicorn on port 8088.
  - Waits a few seconds for server startup.
  - Runs `python -m scripts.demo_full_e2e_real`.
  - On failure, prints basic process info for troubleshooting.
  - Stops the API server using the PID stored in `uvicorn.pid`.

> Note: The workflow does **not** modify the existing CI pipeline. It
> is an additional workflow focused on demonstration.

### 3. GitHub Actions workflow (v2 – production simulated)

- Path: `.github/workflows/ci_full_e2e_demo_v2.yml`
- Trigger: `workflow_dispatch` (manual execution only).
- Jobs (single job: `demo-e2e-v2`):
  - Declares a **Qdrant service** using `services:` so the runner has a
    running vector store.
  - Installs the project under `./new`.
  - Waits for Qdrant health to be ready on port `6333`.
  - Runs the ingestion script:
    - `python -c "from cortex_ka.scripts.ingest_docs import ingest_banking_corpus; ingest_banking_corpus('corpus_bancario_completo.jsonl')"`
    - Uses `corpus_bancario_completo.jsonl` at the project root.
    - Uses `CKA_QDRANT_URL` and `CKA_QDRANT_API_KEY` to connect to the
      Qdrant service inside the job.
  - Starts the API server with:
    - `CKA_USE_QDRANT=true`.
    - `CKA_LLM_PROVIDER=HF`.
    - `CKA_DLP_ENABLED=true`.
    - Qdrant endpoint pointing at the service (`http://localhost:6333`).
  - Runs the demo script with:
    - `CKA_DEMO_VARIANT=v2`.
    - `CKA_DEMO_BASE_URL=http://127.0.0.1:8089`.
  - Performs the same invariants as v1 (HF provider healthy, no PII
    leakage, `used_chunks`/`citations` present), but now answers are
    grounded on the ingested banking corpus stored in Qdrant.

## How to run the demo in GitHub Actions

Prerequisites:

- The repository must have a secret named `HF_API_KEY` with a valid
  Hugging Face token that has permission to call **Inference
  Providers** via the HF router.

Steps:

1. Go to your repository in GitHub.
2. Navigate to **Actions**.
3. Locate the workflow named `Full E2E Demo (HF + RAG + DLP)`.
4. Click **Run workflow**.
5. Select the branch (typically `main` or `develop`) and click the
   second **Run workflow**.

During the run, the job will:

- Spin up the API service.
- Execute the demo script.
- Emit the full JSON responses for the three `/query` calls into the
  job logs.

If everything is correct, the job will finish successfully without
PII leaks in the answers.

## Local usage (optional)

You can also run the demo locally if:

- You have HF credentials (`HF_API_KEY`) exported in your shell.
- You have the API running locally (e.g. via `make run`).

Example:

```bash
cd new
. .venv/bin/activate
export HF_API_KEY=hf_...            # no lo subas al repo
export CKA_LLM_PROVIDER=HF
export CKA_DLP_ENABLED=true
export CKA_USE_QDRANT=false         # o true si tienes Qdrant listo
export CKA_API_KEY=demo-key-cli-81093
export CKA_DEMO_BASE_URL=http://localhost:8000

python -m scripts.demo_full_e2e_real
```

This local example uses the standard demo user with DLP redaction
enabled. If you switch `CKA_API_KEY` to the privileged demo key you
may observe different DLP behaviour; do this only in tightly
controlled lab environments.

## Security guarantees demonstrated

The demo showcases the following aspects of the system:

- **Real LLM provider (HF)** in use for `/query`.
- **DLP active**: PII tokens (DNI, card number) supplied in the query
  do not appear literally in the `answer` for standard users
  (`dlp_level="standard"`). Privileged users (based on
  `CurrentUser.dlp_level`) are out of scope for this demo and must be
  handled via strict IAM policies.
- **Structured logging**: server logs include `request_id`, `trace_id`,
  `span_id` and security metadata suitable for audit.
- **API key authentication**: each `/query` call includes
  `X-CKA-API-Key` and the backend validates the key.
- **RAG structure**: responses include `used_chunks` and
  `citations`. In this workflow the demo uses the stub retriever;
  however, the architecture is the same as in real Qdrant mode.

For a future fully production-aligned demo, you can enable
`CKA_USE_QDRANT=true` and add Qdrant initialization (with a synthetic
banking corpus) before running the demo.
