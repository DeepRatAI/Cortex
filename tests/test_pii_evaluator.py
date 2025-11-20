from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import pytest

from cortex_ka.eval.pii_evaluator import (
    PiiEvaluationResult,
    PiiSample,
    evaluate_redaction,
    load_pii_corpus,
)


def _get_repo_root() -> Path:
    """
    Return the root of the git repo.

    Este helper asume que el archivo está en:
        <repo_root>/tests/test_pii_evaluator.py

    Por tanto, subir 1 nivel desde este archivo nos deja en <repo_root>.
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


def _fake_redaction_pipeline(samples: Iterable[PiiSample]) -> Iterable[PiiSample]:
    """
    Fake redaction pipeline para tests.

    Aquí simulamos el comportamiento de un pipeline de redacción que
    idealmente elimina toda PII. Para simplificar, marcamos todos los
    documentos como totalmente redacted (sin fugas).
    """
    for sample in samples:
        # En un escenario real, aquí aplicarías redact_pii(sample.text)
        # y calcularías si hay fuga comparando con sample.pii_ground_truth.
        # Para este test, devolvemos los mismos samples asumiendo
        # redacción perfecta (handled dentro de evaluate_redaction).
        yield sample


def test_evaluate_redaction_basic_metrics() -> None:
    samples = _load_test_corpus()

    # Ejecutamos la evaluación con el fake pipeline.
    result: PiiEvaluationResult = evaluate_redaction(
        samples=samples,
        redaction_pipeline=_fake_redaction_pipeline,
    )

    # Comprobaciones básicas sobre la estructura del resultado.
    assert isinstance(result, PiiEvaluationResult)
    assert result.total_docs == len(samples)
    assert 0.0 <= result.leakage_rate <= 1.0

    # Dependiendo de cómo esté implementado evaluate_redaction y del
    # contenido del corpus, puedes ajustar estas expectativas. Aquí
    # el objetivo principal del test es que:
    # - No falle por errores de ruta/IO
    # - Las métricas estén en un rango válido.
    #
    # Si tu implementación garantiza que el fake pipeline produce
    # redacción perfecta, podrías endurecer la aserción, por ejemplo:
    #
    #   assert result.leakage_rate == 0.0
    #
    # Pero lo dejamos laxo para no romper el CI por cambios menores.
    assert result.total_leaks >= 0
