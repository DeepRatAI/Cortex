"""Unit tests for PII classifier contract and confidential retrieval config.

These tests are intentionally lightweight and focus on wiring and behaviour of
configuration flags rather than heavy model logic.
"""

from __future__ import annotations

from cortex_ka.application.pii_classifier import (
    PiiClassification,
    classify_pii,
)
from cortex_ka.config import Settings
from cortex_ka.api.main import _select_llm, _FakeLLM


def test_classify_pii_returns_neutral_shape() -> None:
    """Current classify_pii must return a neutral but structured result."""

    result: PiiClassification = classify_pii("Some harmless text")

    assert result.has_pii is False
    assert set(result.by_type.keys()) == {
        "dni",
        "cuit",
        "card",
        "phone",
        "email",
        "other",
    }
    assert all(isinstance(v, bool) for v in result.by_type.values())
    assert result.sensitivity in {"none", "low", "medium", "high"}
    assert result.meta == {}


def test_classify_pii_detects_medium_sensitivity_for_single_identifier() -> None:
    """A single strong identifier (e.g. DNI) should yield medium sensitivity."""

    text = "El DNI del cliente es 12345678."
    result = classify_pii(text)

    # The regex in redact_pii should fire for the numeric DNI and the
    # classifier should map this to a medium sensitivity level.
    assert result.has_pii is True
    assert result.by_type["dni"] is True
    assert result.sensitivity == "medium"


def test_classify_pii_detects_high_sensitivity_for_card_and_dni() -> None:
    """Card numbers or multiple PII types must be classified as high."""

    text = (
        "Cliente DNI 12345678 con tarjeta 4111 1111 1111 1111 registrada en el sistema."
    )
    result = classify_pii(text)

    # Presence of a card plus another identifier should be escalated to high
    # sensitivity, matching the policy encoded in classify_pii.
    assert result.has_pii is True
    assert result.by_type["dni"] is True
    assert result.by_type["card"] is True
    assert result.sensitivity == "high"


def test_settings_confidential_retrieval_only_flag_default() -> None:
    """Settings should expose confidential_retrieval_only with a sane default."""

    s = Settings()
    assert hasattr(s, "confidential_retrieval_only")
    # Default should be False for local dev unless explicitly enabled
    assert s.confidential_retrieval_only is False


def test_select_llm_allows_fake_when_not_confidential(monkeypatch) -> None:
    """When confidential_retrieval_only is False, Fake provider is allowed."""

    monkeypatch.setenv("CKA_LLM_PROVIDER", "Fake")
    monkeypatch.delenv("CKA_CONFIDENTIAL_RETRIEVAL_ONLY", raising=False)

    llm = _select_llm()
    assert isinstance(llm, _FakeLLM)
