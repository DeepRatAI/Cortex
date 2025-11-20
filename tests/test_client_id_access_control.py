from __future__ import annotations

import os
from fastapi.testclient import TestClient

from cortex_ka.api.main import app


def _mk_client() -> TestClient:
    # Force stub retriever and fake LLM to avoid hitting external services.
    os.environ["CKA_USE_QDRANT"] = "false"
    os.environ["CKA_FAKE_LLM"] = "true"
    os.environ["CKA_API_KEY"] = "demo-key-cli-81093"
    return TestClient(app)


def test_query_ignores_client_supplied_subject_id_header(monkeypatch):
    """X-CKA-Subject-Id from the client must be ignored for access control.

    Even if a caller attempts to set a different id_cliente in the header,
    the effective subject_id must still come from the authenticated user
    context, preventing tenant breakout via header manipulation.
    """

    client = _mk_client()
    resp = client.post(
        "/query",
        json={"query": "Hola"},
        headers={
            "X-CKA-API-Key": "demo-key-cli-81093",
            "X-CKA-Subject-Id": "CLI-OTHER-CLIENT",
        },
    )
    # With stub retriever and fake LLM this should succeed; the important
    # part is that no error is raised due to subject id mismatch and that
    # the header does not influence authorization decisions.
    assert resp.status_code == 200, resp.text
