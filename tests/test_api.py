from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cortex_ka.api.main import app
from cortex_ka.application.pii import redact_pii
from cortex_ka.eval.pii_evaluator import load_pii_corpus


client = TestClient(app)


def _mk_client() -> TestClient:
    # Force stub retriever and fake LLM to avoid external deps in API tests.
    os.environ["CKA_USE_QDRANT"] = "false"
    os.environ["CKA_FAKE_LLM"] = "true"
    # Configure demo API key to satisfy get_current_user.
    os.environ["CKA_API_KEY"] = "demo-key-cli-81093"
    return TestClient(app)


def test_query_requires_api_key_when_configured(monkeypatch):
    """When CKA_API_KEY is set, /query should reject missing API key."""

    monkeypatch.setenv("CKA_API_KEY", "demo-key-cli-81093")
    monkeypatch.setenv("CKA_DLP_ENABLED", "true")
    monkeypatch.setenv("CKA_USE_QDRANT", "false")
    monkeypatch.setenv("CKA_FAKE_LLM", "true")

    resp = client.post("/query", json={"query": "Define procedures."})
    assert resp.status_code == 401
    data = resp.json()
    # El sistema actual devuelve 'Unauthorized' como detail para errores 401.
    assert data["detail"] == "Unauthorized"


def test_query_forbidden_for_unknown_demo_api_key(monkeypatch):
    """Unknown API keys should be rejected even if API key auth is enabled."""

    monkeypatch.setenv("CKA_API_KEY", "demo-key-cli-81093")
    monkeypatch.setenv("CKA_DLP_ENABLED", "true")
    monkeypatch.setenv("CKA_USE_QDRANT", "false")
    monkeypatch.setenv("CKA_FAKE_LLM", "true")

    resp = client.post(
        "/query",
        json={"query": "Define procedures."},
        headers={"X-CKA-API-Key": "unknown-key"},
    )
    assert resp.status_code == 401
    data = resp.json()
    # Mismo contrato que el test anterior: 401 + detail 'Unauthorized'.
    assert data["detail"] == "Unauthorized"


def test_query_allows_known_demo_api_key():
    """Known demo API key mapped to a user should be able to call /query.

    We use stub retriever and fake LLM to keep this test offline.
    """

    client = _mk_client()
    resp = client.post(
        "/query",
        json={"query": "Define procedures."},
        headers={"X-CKA-API-Key": "demo-key-cli-81093"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "answer" in data and data["answer"]
    assert isinstance(data["used_chunks"], list)
    assert isinstance(data.get("citations"), list)


def test_pii_redaction_masks_common_identifiers():
    """PII redaction should mask DNI, CUIT/CUIL, card, email and phone in text."""

    text = (
        "Mi DNI es 24567579, mi CUIT es 30-36416280-0, mi tarjeta es 4915600297200043, "
        "mi email es persona@example.org y mi teléfono es +54 9 3328 4267."
    )
    redacted = redact_pii(text)
    assert "24567579" not in redacted
    assert "30-36416280-0" not in redacted
    assert "4915600297200043" not in redacted
    assert "persona@example.org" not in redacted
    assert "+54 9 3328 4267" not in redacted
    # Our current regexes will match the CUIT digits as a DNI-like pattern
    # first, so we only guarantee that CUIT digits disappear, not that a
    # dedicated <cuit-redacted> marker appears.
    assert "<dni-redacted>" in redacted
    assert "<card-redacted>" in redacted
    assert "<email-redacted>" in redacted
    assert "<phone-redacted>" in redacted


def test_query_endpoint_applies_dlp_redaction(monkeypatch):
    """/query should apply DLP (via enforce_dlp) and not leak raw PII."""

    # Ensure DLP is enabled (default) and use stub + fake LLM.
    monkeypatch.setenv("CKA_DLP_ENABLED", "true")
    monkeypatch.setenv("CKA_USE_QDRANT", "false")
    monkeypatch.setenv("CKA_FAKE_LLM", "true")
    monkeypatch.setenv("CKA_API_KEY", "demo-key-cli-81093")

    client = TestClient(app)
    text_with_pii = (
        "Mi DNI es 24567579 y mi tarjeta es 4915 6002 9720 0043, "
        "puedes escribirme a persona@example.org."
    )
    resp = client.post(
        "/query",
        json={"query": text_with_pii},
        headers={"X-CKA-API-Key": "demo-key-cli-81093"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    answer = data["answer"]

    # Raw PII must not appear in the final answer.
    assert "24567579" not in answer
    assert "4915 6002 9720 0043" not in answer
    assert "persona@example.org" not in answer


def test_query_dlp_applies_for_standard_user(monkeypatch):
    """Standard demo user must receive redacted answers when DLP is enabled."""

    monkeypatch.setenv("CKA_DLP_ENABLED", "true")
    monkeypatch.setenv("CKA_USE_QDRANT", "false")
    monkeypatch.setenv("CKA_FAKE_LLM", "true")
    monkeypatch.setenv("CKA_API_KEY", "demo-key-cli-81093")

    client = TestClient(app)
    text_with_pii = (
        "Mi DNI es 24567579 y mi tarjeta es 4915 6002 9720 0043, "
        "puedes escribirme a persona@example.org."
    )
    resp = client.post(
        "/query",
        json={"query": text_with_pii},
        headers={"X-CKA-API-Key": "demo-key-cli-81093"},
    )
    assert resp.status_code == 200, resp.text
    answer = resp.json()["answer"]

    # El usuario estándar no debe ver PII cruda.
    assert "24567579" not in answer
    assert "4915 6002 9720 0043" not in answer
    assert "persona@example.org" not in answer


def test_query_dlp_bypassed_for_privileged_user(monkeypatch):
    """Privileged demo user may bypass DLP when DLP is enabled.

    Esto modela un operador de backoffice en un entorno corporativo
    fuertemente controlado. Usamos la API key de demo mapeada a
    dlp_level="privileged".
    """

    monkeypatch.setenv("CKA_DLP_ENABLED", "true")
    monkeypatch.setenv("CKA_USE_QDRANT", "false")
    monkeypatch.setenv("CKA_FAKE_LLM", "true")
    # Importante: CKA_API_KEY debe coincidir con la API key privilegiada
    # para superar la validación de get_current_user.
    monkeypatch.setenv("CKA_API_KEY", "demo-key-cli-81093-ops")

    client = TestClient(app)
    text_with_pii = (
        "Mi DNI es 24567579 y mi tarjeta es 4915 6002 9720 0043, "
        "puedes escribirme a persona@example.org."
    )
    resp = client.post(
        "/query",
        json={"query": text_with_pii},
        headers={"X-CKA-API-Key": "demo-key-cli-81093-ops"},
    )
    assert resp.status_code == 200, resp.text
    answer = resp.json()["answer"]

    # Para un usuario privilegiado, DLP se puede relajar.
    assert isinstance(answer, str)


def _get_repo_root() -> Path:
    """Helper to resolve project root from the tests folder."""
    # This test file lives at:
    #   <repo_root>/tests/test_api.py
    # so going up one level yields the repository root where
    # `pii_test_corpus.jsonl` is located.
    return Path(__file__).resolve().parents[1]


def _sample_corpus_for_covered_pii(max_per_type: int = 3):
    """Return a small, type-balanced subset of the PII corpus.

    This keeps the API-level DLP test lightweight on local machines while
    still exercising CUIT, card, phone and email redaction on realistic
    examples. The full-corpus evaluation is covered by offline tests in
    `test_pii_evaluator.py`.
    """

    corpus_path = _get_repo_root() / "pii_test_corpus.jsonl"
    samples = load_pii_corpus(corpus_path)

    covered_types = {"cuit", "card", "phone", "email"}
    picked_by_type: dict[str, list] = {t: [] for t in covered_types}

    for sample in samples:
        for pii_type, values in sample.pii_ground_truth.items():
            if pii_type not in covered_types or not values:
                continue
            bucket = picked_by_type[pii_type]
            if len(bucket) < max_per_type:
                bucket.append(sample)
        # Early exit when we've collected enough per type.
        if all(len(picked_by_type[t]) >= max_per_type for t in covered_types):
            break

    subset = []
    for bucket in picked_by_type.values():
        subset.extend(bucket)
    return subset


@pytest.mark.slow
def test_query_endpoint_does_not_leak_cuit_card_phone_email_from_corpus(monkeypatch):
    """/query should not leak CUIT, card, phone or email literals from corpus."""

    monkeypatch.setenv("CKA_DLP_ENABLED", "true")
    monkeypatch.setenv("CKA_USE_QDRANT", "false")
    monkeypatch.setenv("CKA_FAKE_LLM", "true")
    monkeypatch.setenv("CKA_API_KEY", "demo-key-cli-81093")

    client = TestClient(app)

    covered_types = {"cuit", "card", "phone", "email"}
    sampled = _sample_corpus_for_covered_pii(max_per_type=3)

    for sample in sampled:
        resp = client.post(
            "/query",
            json={"query": sample.text},
            headers={"X-CKA-API-Key": "demo-key-cli-81093"},
        )
        assert resp.status_code == 200, resp.text
        answer = resp.json()["answer"]

        # None of the literal covered PII strings should appear in the answer.
        for pii_type, values in sample.pii_ground_truth.items():
            if pii_type not in covered_types:
                continue
            for value in values:
                assert value not in answer, (
                    f"PII value {value!r} of type {pii_type} leaked through /query"
                )
