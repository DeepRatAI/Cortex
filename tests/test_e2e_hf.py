import os
from importlib import reload

import pytest
from fastapi.testclient import TestClient

import cortex_ka.api as api_pkg
from cortex_ka.api.main import app


@pytest.mark.skipif(not os.getenv("HF_API_KEY"), reason="HF_API_KEY not configured")
def test_hf_provider_health_ok(monkeypatch):
    """Smoke test: /health funciona cuando usamos HF como proveedor real."""

    # Forzamos a usar HF en lugar del LLM fake
    monkeypatch.setenv("CKA_LLM_PROVIDER", "HF")
    reload(api_pkg)
    from cortex_ka.api.main import app as hf_app  # reload garantiza config actualizada

    client = TestClient(hf_app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    # El contrato mínimo: debe indicar que el backend está sano
    assert data.get("status") == "ok"


@pytest.mark.skipif(not os.getenv("HF_API_KEY"), reason="HF_API_KEY not configured")
def test_hf_query_with_auth_and_rate_limit(monkeypatch):
    """E2E con HF real: auth + rate limit.

    Validamos que:
    - Sin API key → 401 Unauthorized.
    - Con API key válida, la petición no rompe: puede devolver 200 (OK),
      429 (rate limited) o 403 (rechazo controlado del backend / proveedor).

    No aceptamos 5xx ni errores inesperados.
    """

    # Usar HF como proveedor real
    monkeypatch.setenv("CKA_LLM_PROVIDER", "HF")
    # Configuramos una API key demo para este test
    monkeypatch.setenv("CKA_API_KEY", "k1")

    # Recargamos el paquete para que la config de entorno se aplique
    reload(api_pkg)
    from cortex_ka.api.main import app as hf_app  # type: ignore[redefined-outer-name]

    client = TestClient(hf_app)

    # 1) Sin API key → debe ser 401
    r = client.post("/query", json={"query": "hello"})
    assert r.status_code == 401

    # 2) Con API key → aceptamos 200 (OK), 429 (rate limited) o 403 (rechazo controlado)
    r = client.post(
        "/query",
        headers={"X-CKA-API-Key": "k1"},
        json={"query": "hello"},
    )
    assert r.status_code in (200, 429, 403)
