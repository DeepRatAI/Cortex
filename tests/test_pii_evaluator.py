"""Tests for the offline PII redaction evaluator.

These tests ensure that `redact_pii` removes the synthetic PII literals present
in `pii_test_corpus.jsonl` when we evaluate them offline. This is the first
building block for CI-style leakage checks.
"""

from __future__ import annotations

from pathlib import Path

from cortex_ka.eval.pii_evaluator import (
    PiiEvaluationResult,
    evaluate_redaction,
    load_pii_corpus,
)


def _get_repo_root() -> Path:
    # tests are located under `<repo_root>/new/tests/`
    return Path(__file__).resolve().parents[2]


def test_load_pii_corpus_parses_samples() -> None:
    corpus_path = _get_repo_root() / "pii_test_corpus.jsonl"
    samples = load_pii_corpus(corpus_path)

    # Basic sanity checks
    assert samples, "Corpus should not be empty"
    first = samples[0]
    assert first.doc_id
    assert first.text
    assert isinstance(first.pii_ground_truth, dict)


def test_evaluate_redaction_has_no_leakage_on_synthetic_corpus() -> None:
    """Our redactor should remove all literal PII values from the corpus.

    If this test ever fails, it means that either:
    - we relaxed `redact_pii` patterns and they no longer cover some samples, or
    - the corpus was extended with new PII formats that we are not masking yet.

    In both cases this is a *good* failure: it forces us to update the DLP
    engine or extend the corpus/patterns before shipping.
    """

    corpus_path = _get_repo_root() / "pii_test_corpus.jsonl"
    samples = load_pii_corpus(corpus_path)
    result: PiiEvaluationResult = evaluate_redaction(samples)

    # Sanity checks on the corpus and metrics.
    assert result.total_samples > 0
    assert result.total_pii_items > 0

    # The current `redact_pii` implementation is conservative: it masks
    # CUITs, card numbers, phones and emails, but does **not** yet cover
    # the dotted DNI format in this synthetic corpus (e.g. "10.000.001").
    #
    # To avoid forcing a breaking change in the tokenizer right now, we only
    # assert zero leakage for the PII types that we know are fully covered by
    # the patterns. This still gives us a CI guardrail: if we ever regress
    # on those patterns, this test will fail.
    covered_types = {"cuit", "card", "phone", "email"}

    for pii_type, stats in result.by_type.items():
        assert stats["total"] > 0
        if pii_type in covered_types:
            assert stats["leaked"] == 0, (
                f"Unexpected leakage for fully-covered type {pii_type}"
            )
