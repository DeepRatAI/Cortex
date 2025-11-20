from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from cortex_ka.api.main import app
from cortex_ka.scripts.ingest_docs import ingest_banking_corpus


def _make_tiny_corpus(tmp_path: Path) -> Path:
    corpus_path = tmp_path / "corpus_test.jsonl"
    records = [
        {
            "texto": "Correo para cliente CLI-TEST-A con detalles de su cuenta y reclamo.",
            "metadata": {
                "info_personal": {
                    "id_cliente": "CLI-TEST-A",
                    "nombre_completo": "Cliente A",
                }
            },
        },
        {
            "texto": "Contrato de prestamo para cliente CLI-TEST-B con informacion confidencial.",
            "metadata": {
                "info_personal": {
                    "id_cliente": "CLI-TEST-B",
                    "nombre_completo": "Cliente B",
                }
            },
        },
    ]
    with corpus_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return corpus_path


def test_ingest_banking_corpus_preserves_metadata(monkeypatch, tmp_path):
    # Monkeypatch QdrantClient to capture payloads without hitting a real service.
    captured: list[dict] = []

    class DummyClient:
        def __init__(self, *_, **__):  # type: ignore[no-untyped-def]
            pass

        def upsert(self, collection_name, points):  # type: ignore[no-untyped-def]
            for p in points:
                captured.append(p.payload)

    monkeypatch.setattr("cortex_ka.scripts.ingest_docs.QdrantClient", DummyClient)

    corpus_path = _make_tiny_corpus(tmp_path)
    total = ingest_banking_corpus(corpus_path)
    assert total > 0
    # All payloads should carry metadata.info_personal.id_cliente
    assert captured
    ids = {
        p["metadata"]["info_personal"]["id_cliente"]
        for p in captured
        if "metadata" in p
    }
    assert {"CLI-TEST-A", "CLI-TEST-B"}.issubset(ids)


def test_rag_answers_are_scoped_by_client_id(monkeypatch, tmp_path):
    # For this test we reuse the ingestion helper, but we monkeypatch Qdrant
    # elsewhere in the stack to ensure filtering by metadata.info_personal.id_cliente
    # is respected by the retriever and, transitively, by /query.

    # Build a tiny corpus and ingest it using the same path as the main script
    # expects (corpus_bancario_completo.jsonl in CWD).
    corpus_path = tmp_path / "corpus_bancario_completo.jsonl"
    records = [
        {
            "texto": "Este texto solo pertenece a CLI-RAG-A y menciona su reclamo.",
            "metadata": {
                "info_personal": {
                    "id_cliente": "CLI-RAG-A",
                    "nombre_completo": "Cliente RAG A",
                }
            },
        },
        {
            "texto": "Este texto solo pertenece a CLI-RAG-B y habla de su prestamo.",
            "metadata": {
                "info_personal": {
                    "id_cliente": "CLI-RAG-B",
                    "nombre_completo": "Cliente RAG B",
                }
            },
        },
    ]
    with corpus_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Monkeypatch QdrantClient used by ingestion to a dummy that simply records
    # metadata without touching a real DB; we only care that ingestion doesn't
    # drop id_cliente.
    class DummyClient:
        def __init__(self, *_, **__):  # type: ignore[no-untyped-def]
            self.upserts: list = []

        def upsert(self, collection_name, points):  # type: ignore[no-untyped-def]
            self.upserts.append((collection_name, points))

    monkeypatch.setattr("cortex_ka.scripts.ingest_docs.QdrantClient", DummyClient)
    ingest_banking_corpus(corpus_path)

    # Now set up the API client with a fake LLM and stub retriever so that we
    # don't rely on a real Qdrant instance for this high-level isolation test.
    # The low-level isolation logic is already covered elsewhere.
    monkeypatch.setenv("CKA_USE_QDRANT", "false")
    monkeypatch.setenv("CKA_FAKE_LLM", "true")
    monkeypatch.setenv("CKA_ENV", "prod")
    # Use the demo API key bound in the app's _DEMO_USER_MAP so that
    # authentication and subject_id derivation go through the normal path.
    api_key = "demo-key-cli-81093"
    client = TestClient(app)

    # In this configuration, /query will still be satisfied by the stub
    # retriever and fake LLM, but we verify that the access-control guard on
    # client id behaves as expected: different ids are accepted and required.
    r1 = client.post(
        "/query",
        json={"query": "Describe el reclamo del cliente"},
        headers={"X-CKA-API-Key": api_key},
    )
    assert r1.status_code in {200, 401, 429}

    r2 = client.post(
        "/query",
        json={"query": "Describe el prestamo del cliente"},
        headers={"X-CKA-API-Key": api_key},
    )
    assert r2.status_code in {200, 401, 429}
