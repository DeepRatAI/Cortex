from __future__ import annotations
from cortex_ka.infrastructure.retriever_qdrant import QdrantRetriever


class DummyClient:
    def __init__(self, *args, **kwargs):
        # Mimic QdrantClient without network
        pass

    def query_points(self, *args, **kwargs):  # type: ignore[unused-argument]
        raise RuntimeError("network down")


def test_qdrant_retriever_error_path(monkeypatch):
    # Replace underlying client with dummy that raises
    r = QdrantRetriever(collection="demo", top_k=2)
    monkeypatch.setattr(r, "_client", DummyClient())
    result = r.retrieve("test")
    assert result.chunks == []
    assert result.query == "test"
