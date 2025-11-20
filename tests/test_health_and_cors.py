from __future__ import annotations
from fastapi.testclient import TestClient
from cortex_ka.api.main import app


def test_health_ok():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_cors_headers_present():
    client = TestClient(app)
    r = client.options(
        "/query",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.headers.get("access-control-allow-origin") is not None
