from __future__ import annotations
import time
import pytest
from fastapi.testclient import TestClient
from cortex_ka.api.main import app


@pytest.mark.streaming
def test_streaming_disabled_by_default():
    client = TestClient(app)
    # Without API key auth now fails with 401/403 before checking streaming flag.
    # For this test we explicitly send a valid demo API key so that the handler
    # can proceed to the streaming-enabled check and return 404 by default.
    r = client.get(
        "/chat/stream?q=hello",
        headers={"X-CKA-API-Key": "demo-key-cli-81093"},
    )
    assert r.status_code == 404


@pytest.mark.streaming
def test_streaming_enabled_and_yields(monkeypatch):
    monkeypatch.setenv("CKA_ENABLE_STREAMING", "true")
    # re-import not strictly necessary if handler checks env per-call
    client = TestClient(app)
    with client.stream(
        "GET",
        "/chat/stream?q=hello",
        headers={"X-CKA-API-Key": "demo-key-cli-81093"},
    ) as r:
        assert r.status_code == 200
        # Read a few lines to verify Server-Sent Events format
        lines = []
        start = time.time()
        for line in r.iter_lines():
            if line:
                lines.append(
                    line.decode() if isinstance(line, (bytes, bytearray)) else line
                )
            if len(lines) >= 3 or time.time() - start > 1.0:
                break
        assert any(str(part).startswith("data:") for part in lines)


@pytest.mark.streaming
def test_streaming_applies_dlp_redaction(monkeypatch):
    """/chat/stream should not leak raw PII when DLP is enabled."""

    monkeypatch.setenv("CKA_ENABLE_STREAMING", "true")
    monkeypatch.setenv("CKA_DLP_ENABLED", "true")
    monkeypatch.setenv("CKA_USE_QDRANT", "false")
    monkeypatch.setenv("CKA_FAKE_LLM", "true")
    monkeypatch.setenv("CKA_API_KEY", "demo-key-cli-81093")

    client = TestClient(app)
    text_with_pii = (
        "Mi DNI es 24567579 y mi tarjeta es 4915600297200043, "
        "mi email es persona@example.org."
    )
    with client.stream(
        "GET",
        f"/chat/stream?q={text_with_pii}",
        headers={"X-CKA-API-Key": "demo-key-cli-81093"},
    ) as r:
        assert r.status_code == 200
        collected = ""
        start = time.time()
        for line in r.iter_lines():
            if not line:
                continue
            s = line.decode() if isinstance(line, (bytes, bytearray)) else str(line)
            if s.startswith("data:"):
                collected += s
            if len(collected) > 200 or time.time() - start > 2.0:
                break

        # Raw PII should not appear in the streamed data.
        assert "24567579" not in collected
        assert "4915600297200043" not in collected
        assert "persona@example.org" not in collected
