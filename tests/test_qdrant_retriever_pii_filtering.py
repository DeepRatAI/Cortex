from __future__ import annotations

from cortex_ka.infrastructure.retriever_qdrant import QdrantRetriever


class DummyHit:
    """Minimal stand-in for a Qdrant point hit.

    It only exposes the `payload` and `id` attributes the retriever uses.
    """

    def __init__(self, pid: str, payload: dict):
        self.id = pid
        self.payload = payload


def test_qdrant_retriever_skips_high_sensitivity_chunks(monkeypatch):
    """Retriever should drop chunks whose payload is marked as high sensitivity.

    This exercises the in-process filtering logic without requiring a live
    Qdrant instance.
    """

    # Arrange a retriever but monkeypatch the underlying client.search call
    r = QdrantRetriever(collection="demo", top_k=5)

    high = DummyHit(
        "1",
        {
            "text": "PAN 4111-1111-1111-1111",
            "source": "test",
            "pii": {"sensitivity": "high", "has_pii": True},
        },
    )
    medium = DummyHit(
        "2",
        {
            "text": "DNI 12345678",
            "source": "test",
            "pii": {"sensitivity": "medium", "has_pii": True},
        },
    )
    none = DummyHit(
        "3",
        {
            "text": "Corporate policy text",
            "source": "test",
            "pii": {"sensitivity": "none", "has_pii": False},
        },
    )

    monkeypatch.setattr(
        r,
        "_client",
        type(
            "DummyClient",
            (),
            {"search": lambda *_args, **_kwargs: [high, medium, none]},
        ),
    )

    result = r.retrieve("test query", k=5, subject_id=None)

    # Only medium and none should survive; high-sensitivity chunk must be skipped.
    texts = [c.text for c in result.chunks]
    assert "PAN 4111-1111-1111-1111" not in texts
    assert "DNI 12345678" in texts
    assert "Corporate policy text" in texts

    # The retriever should propagate pii_sensitivity into DocumentChunk for
    # downstream observability/auditing.
    sensitivities = {c.text: c.pii_sensitivity for c in result.chunks}
    assert sensitivities["DNI 12345678"] == "medium"
    assert sensitivities["Corporate policy text"] == "none"
