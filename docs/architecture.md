# Architecture

The system follows a layered/hexagonal architecture:

- Presentation: FastAPI endpoints (`src/cortex_ka/api`)
- Application: Orchestration (`src/cortex_ka/application`)
- Domain: Models and ports (`src/cortex_ka/domain`)
- Infrastructure: Adapters (`src/cortex_ka/infrastructure`)

Adapters present stable ports for retrieval, LLM, embedding, and caching. Domain layer is framework-agnostic, enabling future swap of components (e.g., different vector DB or LLM provider).

Planned enhancements:

- Replace stub retriever with Qdrant adapter
- Add embedding microservice or reuse local model behind an async interface
- Introduce conversation memory store with TTL and trace IDs

## Qdrant Schema

Collection: `corporate_docs`

Named vector: `text` (COSINE distance, size determined from embedding model at init).
Payload fields used currently:

- `text`: chunk content
- `source`: synthetic document source identifier

Future payload enrichment may include:

- `doc_id`, `chunk_index`, `created_at`, classification tags, sensitivity level.

## Ingestion Pipeline

1. Initialize collection (see `scripts/init_qdrant.py`).
2. Load raw synthetic documents (internal manuals, policies, etc.).
3. Chunking (`simple_chunks`) by approximate character length aiming for <=400 chars.
4. Embedding via local sentence-transformers model.
5. Upsert to Qdrant with deterministic IDs (document id + chunk index + random suffix).
6. Retrieval uses `query_points` with a NamedVector and returns top-k matches.

## Prompt Assembly

Application service concatenates chunk texts as bullet points. Future improvements:

- Add citation markers referencing chunk IDs.
- Implement prompt length guardrails (truncate or summarize context if > token budget).
- Streaming responses for large generations.
