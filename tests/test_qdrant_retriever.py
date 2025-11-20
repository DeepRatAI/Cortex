from __future__ import annotations
from cortex_ka.infrastructure.retriever_qdrant import QdrantRetriever


def test_qdrant_retriever_returns_empty_when_unavailable(monkeypatch):
    # Point to an unreachable URL to simulate unavailable service
    monkeypatch.setenv("CKA_QDRANT_URL", "http://unreachable-qdrant:6333")
    r = QdrantRetriever(collection="test_collection", top_k=3)
    result = r.retrieve("test query", k=3)
    assert result.query == "test query"
    assert isinstance(result.chunks, list)
    assert len(result.chunks) == 0
