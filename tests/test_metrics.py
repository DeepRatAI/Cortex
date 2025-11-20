from __future__ import annotations
from fastapi.testclient import TestClient
from cortex_ka.api.main import app


def test_metrics_endpoint_exposes_prometheus_text():
    client = TestClient(app)
    r = client.get("/metrics")
    assert r.status_code == 200
    # Prometheus exposition format starts with '# HELP' or '# TYPE' lines
    assert any(line.startswith("# ") for line in r.text.splitlines())
