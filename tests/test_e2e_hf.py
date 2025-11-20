from __future__ import annotations
import os
from importlib import reload
import pytest
from fastapi.testclient import TestClient
from cortex_ka import api as api_pkg

pytestmark = pytest.mark.e2e


@pytest.mark.skipif(not os.getenv("HF_API_KEY"), reason="HF_API_KEY not configured")
def test_hf_provider_health_ok(monkeypatch):
    monkeypatch.setenv("CKA_LLM_PROVIDER", "HF")
    reload(api_pkg)
    from cortex_ka.api.main import app

    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["provider"] == "hf"
    assert "provider_ok" in data


@pytest.mark.skipif(not os.getenv("HF_API_KEY"), reason="HF_API_KEY not configured")
def test_hf_query_with_auth_and_rate_limit(monkeypatch):
    monkeypatch.setenv("CKA_LLM_PROVIDER", "HF")
    monkeypatch.setenv("CKA_API_KEY", "k1")
    reload(api_pkg)
    from cortex_ka.api.main import app

    client = TestClient(app)
    # Unauthorized
    r = client.post("/query", json={"query": "hello"})
    assert r.status_code == 401
    # Authorized
    r = client.post("/query", headers={"X-CKA-API-Key": "k1"}, json={"query": "hello"})
    assert r.status_code in (200, 429)
    if r.status_code == 200:
        assert "answer" in r.json()
