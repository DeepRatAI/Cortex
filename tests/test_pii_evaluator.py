from __future__ import annotations

from pathlib import Path
from typing import List

from cortex_ka.eval.pii_evaluator import (
    PiiEvaluationResult,
    PiiSample,
    evaluate_redaction,
    load_pii_corpus,
)


def _get_repo_root() -> Path:
    """
    Devuelve la raíz del repo.

    Asumimos que este archivo está en:
        <repo_root>/tests/test_pii_evaluator.py

    Así que subir 1 nivel nos deja en <repo_root>.
    """
    return Path(__file__).resolve().parents[1]


def _load_test_corpus() -> List[PiiSample]:
    repo_root = _get_repo_root()
    corpus_path = repo_root / "pii_test_corpus.jsonl"

    if not corpus_path.exists():
        raise FileNotFoundError(
            f"Expected PII test corpus at {corpus_path}, "
            "but the file does not exist. Ensure 'pii_test_corpus.jsonl' "
            "is located at the repository root."
        )

    return load_pii_corpus(corpus_path)


def test_load_pii_corpus_ok() -> None:
    samples = _load_test_corpus()

    # Sanity checks sobre el corpus
    assert isinstance(samples, list)
    assert samples, "PII corpus should not be empty"

    first = samples[0]
    assert isinstance(first, PiiSample)
    assert isinstance(first.doc_id, str)
    assert isinstance(first.text, str)
    assert isinstance(first.pii_ground_truth, dict)


def test_evaluate_redaction_basic_metrics() -> None:
    samples = _load_test_corpus()

    # Ejecutamos la evaluación usando el redactor real (redact_pii)
    result: PiiEvaluationResult = evaluate_redaction(samples)

    # Comprobaciones básicas sobre la estructura del resultado.
    assert isinstance(result, PiiEvaluationResult)
    assert result.total_samples == len(samples)
    assert 0.0 <= result.leakage_rate <= 1.0
    assert result.total_pii_items >= 0
    assert result.leaked_items >= 0

    # by_type debe tener el mismo soporte que los tipos del corpus
    if samples and samples[0].pii_ground_truth:
        # No exigimos un valor concreto, solo que la estructura tenga sentido
        assert isinstance(result.by_type, dict)
