# Cortex Knowledge Assistant

> Operational runbook for the synthetic banking demo deployment.

## 1. Overview

This runbook describes the canonical operational flow for running the
Cortex Knowledge Assistant (CKA) in a synthetic banking scenario:

1. Start Qdrant.
2. Ensure environment variables are configured.
3. Ingest the synthetic banking corpus into Qdrant.
4. Start the FastAPI application.
5. Run health checks and sample queries.

The same flow underpins both local runs and CI E2E demo workflows.

## 2. Environment configuration

### 2.1 Mandatory variables

At minimum, set the following environment variables (typically via
`.env`):

- `CKA_API_KEY` – API key required for `/query`.
- `CKA_LLM_PROVIDER` – usually `HF` for Hugging Face.
- `HF_API_KEY` – your Hugging Face token (never commit this).
- `CKA_DLP_ENABLED` – `true` in banking‑like environments.
- `CKA_USE_QDRANT` – `true` to enable real RAG.
- `CKA_QDRANT_URL` – base URL for Qdrant (e.g. `http://localhost:6333`).

Optional but recommended:

- `CKA_QDRANT_COLLECTION_DOCS` – Qdrant collection name
  (default `corporate_docs`).
- `CKA_EMBEDDING_MODEL` – SentenceTransformers model name.

### 2.2 Loading .env

```bash
cd new
source .venv/bin/activate
set -a; source .env; set +a
```

## 3. Start Qdrant

For local development, start Qdrant as a Docker container publishing
port `6333`:

```bash
docker run --rm -p 6333:6333 qdrant/qdrant:latest
```

Verify health:

```bash
curl http://localhost:6333/healthz
```

In Kubernetes or docker‑compose environments, point `CKA_QDRANT_URL` to
the service DNS name instead (e.g. `http://qdrant:6333`).

## 4. Ingest the synthetic banking corpus

The canonical ingestion entrypoint is `cortex_ka.scripts.ingest_docs`.
For the built‑in synthetic banking corpus:

```bash
cd new
source .venv/bin/activate

python -m cortex_ka.scripts.ingest_docs \
  --input corpus_bancario_completo.jsonl \
  --collection "$CKA_QDRANT_COLLECTION_DOCS"
```

This will:

- Split documents into chunks.
- Embed each chunk with the configured local embedding model.
- Upsert points into the Qdrant collection, preserving
  `metadata.info_personal.id_cliente` for access control.

> Compatibility note: `scripts/ingest_corpus_qdrant.py` is a thin
> **shim** that delegates to the same ingestion path. It exists only to
> avoid breaking older workflows; new flows should use
> `cortex_ka.scripts.ingest_docs` directly.

## 5. Start the API

```bash
cd new
source .venv/bin/activate
set -a; source .env; set +a

uvicorn cortex_ka.api.main:app --host 0.0.0.0 --port 8000
```

### 5.1 Health check

```bash
curl http://localhost:8000/health
```

Expected behavior:

- `status` is `ok`.
- `provider` is `hf` when `CKA_LLM_PROVIDER=HF`.
- `provider_ok` is `true` when HF is reachable and ready.

### 5.2 Sample query

```bash
curl -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -H 'X-CKA-API-Key: demo-key-cli-81093' \
  -d '{"query": "Dame un resumen de mi situación como cliente"}'
```

Expected behavior:

- HTTP 200.
- JSON body with `answer`, `used_chunks`, and `citations`.
- The `answer` is in Spanish, grounded on the ingested corpus, and does
  **not** echo literal PII values.

The `demo-key-cli-81093` API key is mapped to a synthetic demo user with a
"standard" DLP level: answers are redacted so they do not contain raw PII
even if the query includes DNI, CUIT/CUIL, card numbers, emails or phones.

For lab‑only backoffice scenarios there is also a privileged demo API key
(`demo-key-cli-81093-ops`) mapped to a user with a "privileged" DLP level.
This key is intended only for tightly controlled environments where operators
are allowed to see unredacted PII. It MUST NOT be used in public demos or
production‑like environments.

## 6. Security checkpoints

Before exposing the service even in a controlled demo, verify:

1. **API key enforcement**
   - Requests without `X-CKA-API-Key` receive `401`/`403`.
   - Unknown API keys receive `403`.
2. **Subject scoping**
   - `subject_id` is derived exclusively from the authenticated user
     context (`allowed_subject_ids`), not from client headers.
   - Headers such as `X-CKA-Subject-Id` are ignored.
3. **RAG isolation**
   - Queries scoped to different customers return context tied only to
     that customer, based on `metadata.info_personal.id_cliente`.
4. **DLP**
   - For standard users, adversarial prompts that include PII literals do not
     result in the same literals being echoed in `answer`.
   - Only explicitly privileged users (via `CurrentUser.dlp_level`) are
     allowed to see unredacted PII, and even then only in tightly controlled
     backoffice scenarios.

Related tests:

- `tests/test_banking_corpus_ingest_and_rag.py` – ingestion and
  metadata preservation.
- `tests/test_client_id_access_control.py` – access control semantics.
- `tests/test_pii_classifier_and_config.py` – PII classification.

## 7. CI E2E demos

Two manual GitHub Actions workflows exercise the system end‑to‑end
using the same primitives described here:

- `Full E2E Demo (HF + RAG + DLP)` – v1, stub retriever.
- `Full E2E Demo v2 (HF + Qdrant + Corpus + DLP)` – v2, real Qdrant
  with banking corpus.

See `docs/DEMO_FULL_E2E_REAL.md` for details and expected behavior of
these demos.

## 8. Troubleshooting

- **HF health flakiness** – if `/health` reports `provider_ok=false`,
  check `HF_API_KEY`, model access, and account limits.
- **Qdrant connectivity** – verify `CKA_QDRANT_URL` and Qdrant logs.
- **PII leakage suspicions** – inspect logs and confirm DLP
  configuration; add tests mirroring `test_prompt_injection_api` if
  needed.
