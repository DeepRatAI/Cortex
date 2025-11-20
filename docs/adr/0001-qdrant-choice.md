# ADR 0001: Choice of Qdrant for Vector Store

Context: The system requires a vector database supporting similarity search, payload metadata, and easy local deployment.

Decision: Adopt Qdrant due to its mature feature set (named vectors, filters), Docker friendliness, and Python client.

Alternatives Considered:

- FAISS: Lacks built-in persistence & payload management out of the box.
- Chroma: Rapid iteration but less explicit control over schema in some versions.
- Weaviate: Rich feature set but heavier operational footprint for local demo.

Consequences:

- Enables flexible schema evolution via payload keys.
- Simplifies local dev (single container) and integration tests via graceful fallback.
- Requires explicit collection initialization script (`init_qdrant.py`).
