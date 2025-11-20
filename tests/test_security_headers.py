from __future__ import annotations
from fastapi.testclient import TestClient
from importlib import reload
from cortex_ka import api as api_pkg


def test_security_headers_when_https_enabled(monkeypatch):
    monkeypatch.setenv("CKA_HTTPS_ENABLED", "true")
    monkeypatch.setenv("CKA_CSP_POLICY", "default-src 'self'")
    # Reload app to apply settings
    reload(api_pkg)
    from cortex_ka.api.main import app

    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("Strict-Transport-Security") is not None
    assert r.headers.get("Content-Security-Policy") is not None


def test_version_endpoint_schema(monkeypatch):
    from cortex_ka.api.main import app

    client = TestClient(app)
    r = client.get("/version")
    assert r.status_code == 200
    data = r.json()
    assert {"git_sha", "build_time", "app_version"} <= set(data.keys())
