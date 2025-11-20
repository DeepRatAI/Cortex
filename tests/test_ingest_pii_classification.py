from __future__ import annotations

from cortex_ka.scripts.ingest_docs import simple_chunks
from cortex_ka.application.pii_classifier import classify_pii, PiiClassification


def test_simple_chunks_and_classifier_contract():
    """simple_chunks output is accepted by classify_pii and contract is stable.

    This is a lightweight integration test that exercises the hook between the
    ingestion chunker and the PII classifier without touching Qdrant.
    """

    text = (
        "El cliente Juan Perez, DNI 12.345.678, tiene tarjeta VISA terminada en 1234."
    )
    chunks = simple_chunks(text, max_len=80)
    assert chunks, "chunker should return at least one chunk"

    for ch in chunks:
        result = classify_pii(ch)
        assert isinstance(result, PiiClassification)
        assert isinstance(result.has_pii, bool)
        # The classifier must always provide the expected keys so that
        # ingestion can blindly persist them in the payload.
        for key in ("dni", "cuit", "card", "phone", "email", "other"):
            assert key in result.by_type
        assert result.sensitivity in {"none", "low", "medium", "high"}
