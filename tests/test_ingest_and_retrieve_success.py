from __future__ import annotations
from cortex_ka.scripts.ingest_docs import upsert_documents, IngestDoc
from cortex_ka.infrastructure.retriever_qdrant import QdrantRetriever


class DummyQdrant:
    def __init__(self):
        self.upserts = []

    def upsert(self, collection_name, points):  # type: ignore[no-untyped-def]
        # record but do nothing
        self.upserts.append((collection_name, points))

    def search(
        self,
        collection_name,
        query_vector,
        limit,
        query_filter=None,
        with_payload=True,
    ):  # type: ignore[no-untyped-def]
        """Mimic qdrant-client's search API used by QdrantRetriever.

        We ignore the actual vector and collection_name and just return a
        deterministic set of points, optionally filtered by the
        metadata.info_personal.id_cliente field when a Filter is provided.
        """

        class _Point:
            def __init__(self, i, client_id):
                self.id = f"p-{i}"
                self.payload = {
                    "text": f"content-{i}",
                    "source": "demo",
                    "metadata": {"info_personal": {"id_cliente": client_id}},
                }

        points = [
            _Point(1, "cliente-A"),
            _Point(2, "cliente-B"),
        ]

        # Honour Filter/FieldCondition on metadata.info_personal.id_cliente if present.
        if query_filter is not None and getattr(query_filter, "must", None):
            wanted = None
            for cond in query_filter.must:
                if getattr(cond, "key", None) == "metadata.info_personal.id_cliente":
                    match = getattr(cond, "match", None)
                    if match is not None:
                        wanted = getattr(match, "value", None)
            if wanted is not None:
                points = [
                    p
                    for p in points
                    if p.payload["metadata"]["info_personal"]["id_cliente"] == wanted
                ]

        return points[: limit or 10]


def test_upsert_documents_monkeypatched(monkeypatch):
    dummy = DummyQdrant()
    monkeypatch.setattr("cortex_ka.scripts.ingest_docs.QdrantClient", lambda **_: dummy)
    docs = [
        IngestDoc(
            doc_id="d1", source="synth", content="a b c d e f g h i j k l m n o p"
        )
    ]
    total = upsert_documents(docs)
    assert total > 0
    assert len(dummy.upserts) >= 1


def test_retriever_success_path(monkeypatch):
    r = QdrantRetriever(collection="demo", top_k=2)
    dummy = DummyQdrant()
    monkeypatch.setattr(r, "_client", dummy)
    # Explicitly pass a subject id to exercise the id_cliente filter.
    result = r.retrieve("hello", k=2, subject_id="cliente-A")
    assert len(result.chunks) == 1
    assert result.chunks[0].text.startswith("content-1")


def test_retriever_isolation_by_id_cliente(monkeypatch):
    """Ensure that different id_cliente values never mix in retrieval."""
    r = QdrantRetriever(collection="demo", top_k=2)
    dummy = DummyQdrant()
    monkeypatch.setattr(r, "_client", dummy)

    res_a = r.retrieve("hello", k=2, subject_id="cliente-A")
    res_b = r.retrieve("hello", k=2, subject_id="cliente-B")

    assert {c.text for c in res_a.chunks} == {"content-1"}
    assert {c.text for c in res_b.chunks} == {"content-2"}
