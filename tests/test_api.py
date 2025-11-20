from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cortex_ka.api.main import app
from cortex_ka.eval.pii_evaluator import load_pii_corpus


client = TestClient(app)


def test_query_requires_api_key_when_configured(monkeypatch):
    """When CKA_API_KEY is set, /query should reject missing API key."""

    monkeypatch.setenv("CKA_API_KEY", "demo-key-cli-81093")
    monkeypatch.setenv("CKA_DLP_ENABLED", "true")
    monkeypatch.setenv("CKA_USE_QDRANT", "false")
    monkeypatch.setenv("CKA_FAKE_LLM", "true")

    resp = client.post("/query", json={"query": "Define procedures."})
    assert resp.status_code == 401
    data = resp.json()
    assert data["detail"] == "Missing or invalid API key"


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
    assert data["detail"] == "Missing or invalid API key"


def test_query_allows_known_demo_api_key(monkeypatch):
    """Known demo API key should allow access to /query."""

    monkeypatch.setenv("CKA_API_KEY", "demo-key-cli-81093")
    monkeypatch.setenv("CKA_DLP_ENABLED", "true")
    monkeypatch.setenv("CKA_USE_QDRANT", "false")
    monkeypatch.setenv("CKA_FAKE_LLM", "true")

    resp = client.post(
        "/query",
        json={"query": "Define procedures."},
        headers={"X-CKA-API-Key": "demo-key-cli-81093"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # The fake LLM returns deterministic, short answers for tests.
    assert isinstance(data["answer"], str)
    assert data["answer"]


def test_pii_redaction_masks_common_identifiers(monkeypatch):
    """PII redaction should mask typical identifiers in the fake LLM answer."""

    monkeypatch.setenv("CKA_API_KEY", "demo-key-cli-81093")
    monkeypatch.setenv("CKA_DLP_ENABLED", "true")
    monkeypatch.setenv("CKA_USE_QDRANT", "false")
    monkeypatch.setenv("CKA_FAKE_LLM", "true")

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

    # Literal PII should not appear in the answer.
    for literal in [
        "24567579",
        "4915 6002 9720 0043",
        "persona@example.org",
    ]:
        assert literal not in answer


def test_query_endpoint_applies_dlp_redaction(monkeypatch):
    """End-to-end: /query should apply DLP redaction on responses."""

    monkeypatch.setenv("CKA_API_KEY", "demo-key-cli-81093")
    monkeypatch.setenv("CKA_DLP_ENABLED", "true")
    monkeypatch.setenv("CKA_USE_QDRANT", "false")
    monkeypatch.setenv("CKA_FAKE_LLM", "true")

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

    assert isinstance(answer, str)
    for literal in [
        "24567579",
        "4915 6002 9720 0043",
        "persona@example.org",
    ]:
        assert literal not in answer


def test_query_dlp_applies_for_standard_user(monkeypatch):
    """Standard users should always get DLP-enforced answers."""

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

    assert isinstance(answer, str)
    for literal in [
        "24567579",
        "4915 6002 9720 0043",
        "persona@example.org",
    ]:
        assert literal not in answer


def test_query_dlp_bypassed_for_privileged_user(monkeypatch):
    """Privileged users may have DLP relaxed in tightly controlled environments.

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

    # Para un usuario privilegiado, DLP se puede relajar. No afirmamos que
    # el fake LLM copie literalmente el input, pero al menos validamos que
    # la llamada no falle y que la lógica de bypass no rompe el endpoint.
    assert isinstance(answer, str)


def _get_repo_root() -> Path:
    """Helper to resolve project root from the tests folder."""
    # Este archivo vive en:
    #   <repo_root>/tests/test_api.py
    # así que subir un nivel nos deja en la raíz del repo, donde
    # está `pii_test_corpus.jsonl`.
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
    """/query should not leak CUIT, card, phone or email literals from corpus.

    This test intentionally uses only a *small sampled subset* of the synthetic
    PII corpus to keep local runs lightweight. The offline evaluator in
    `test_pii_evaluator.py` is responsible for exercising the full corpus.

    Usage guidance:
    - Local development on modest hardware: run fast tests only, e.g.
      `pytest -m 'not slow'` once this test is marked as slow.
    - CI or powerful environments: include slow tests as well.
    """

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
