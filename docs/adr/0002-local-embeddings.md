# ADR 0002: Local Embeddings Strategy

Context: Embedding generation must be reproducible, offline-capable, and avoid external service dependency for tests.

Decision: Use `sentence-transformers/all-MiniLM-L6-v2` locally via `sentence_transformers` library.

Alternatives:

- Remote API (OpenAI, Azure): Adds latency, external dependency, cost.
- Larger model (e.g., bge-large): Higher quality but higher memory; not needed for demo scope.

Consequences:

- Faster iteration and deterministic embedding dimension.
- Memory footprint manageable in slim container; can switch via env variable.
- Must guard future scaling by introducing async batch interface if concurrency grows.
