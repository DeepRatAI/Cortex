from __future__ import annotations
from fastapi.testclient import TestClient
from cortex_ka.api.main import app


def test_requires_api_key_when_configured(monkeypatch):
    """When an API key is configured, it must also be present in the demo map.

    Our demo auth layer first validates the API key against CKA_API_KEY and then
    checks it against the in-memory _DEMO_USER_MAP. A key that is not mapped to a
    user will still be rejected with 403 even if it matches CKA_API_KEY.
    """

    monkeypatch.setenv("CKA_FAKE_LLM", "true")
    monkeypatch.setenv("CKA_USE_QDRANT", "false")
    # Use the same key that is configured in _DEMO_USER_MAP so that auth passes.
    monkeypatch.setenv("CKA_API_KEY", "demo-key-cli-81093")
    client = TestClient(app)
    # Missing header -> 401
    r = client.post("/query", json={"query": "Hi"})
    assert r.status_code == 401
    # Wrong header -> 401
    r = client.post("/query", headers={"X-CKA-API-Key": "nope"}, json={"query": "Hi"})
    assert r.status_code == 401
    # Correct header and mapped API key -> 200
    r = client.post(
        "/query",
        headers={"X-CKA-API-Key": "demo-key-cli-81093"},
        json={"query": "Hi"},
    )
    assert r.status_code == 200


def test_query_validation(monkeypatch):
    """Validation errors should surface once auth succeeds."""

    monkeypatch.setenv("CKA_FAKE_LLM", "true")
    monkeypatch.setenv("CKA_USE_QDRANT", "false")
    monkeypatch.setenv("CKA_API_KEY", "demo-key-cli-81093")
    client = TestClient(app)
    # Missing/blank query should trigger 422, but we must send a valid API key
    # so that authentication doesn't fail first.
    r = client.post(
        "/query",
        headers={"X-CKA-API-Key": "demo-key-cli-81093"},
        json={"query": "  "},
    )
    assert r.status_code == 422
    r = client.post(
        "/query",
        headers={"X-CKA-API-Key": "demo-key-cli-81093"},
        json={"query": "a" * 3000},
    )
    assert r.status_code == 413
