"""Synthetic ingestion script for Qdrant.

Splits provided text documents into chunks, embeds them, and upserts into Qdrant.
This is a minimal, local-only pipeline intended for demos and tests.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, List
import json
from pathlib import Path
import uuid
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from cortex_ka.config import settings
from cortex_ka.infrastructure.embedding_local import LocalEmbedder
from cortex_ka.logging import logger
from cortex_ka.application.pii_classifier import classify_pii


@dataclass(frozen=True)
class IngestDoc:
    doc_id: str
    content: str
    source: str
    metadata: dict | None = None


def simple_chunks(text: str, max_len: int = 400) -> list[str]:
    words = text.split()
    acc: list[str] = []
    cur: list[str] = []
    for w in words:
        cur.append(w)
        if sum(len(x) + 1 for x in cur) > max_len:
            acc.append(" ".join(cur[:-1]))
            cur = [w]
    if cur:
        acc.append(" ".join(cur))
    return acc


def upsert_documents(docs: Iterable[IngestDoc]) -> int:
    client = QdrantClient(
        url=settings.qdrant_url, api_key=settings.qdrant_api_key or None
    )
    embedder = LocalEmbedder()
    total = 0
    for d in docs:
        chunks = simple_chunks(d.content)
        if not chunks:
            continue
        vectors: List[List[float]] = embedder.embed(chunks)
        points = []
        for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
            # Qdrant expects point ids to be either unsigned integers or UUIDs.
            # We use UUID4 for each chunk to avoid format errors and keep ids
            # opaque. Business identifiers (doc_id, id_cliente, etc.) are kept
            # inside the payload for traceability instead of being encoded in
            # the point id itself.
            pid = str(uuid.uuid4())
            payload: dict = {"text": chunk, "source": d.source, "doc_id": d.doc_id}
            # Attach PII classification metadata for this chunk so that
            # downstream components (retrievers, auditors, policies) can make
            # decisions based on sensitivity without re-scanning raw text.
            try:
                cls = classify_pii(chunk)
                payload["pii"] = {
                    "has_pii": cls.has_pii,
                    "by_type": cls.by_type,
                    "sensitivity": cls.sensitivity,
                }
            except Exception as exc:  # pragma: no cover - defensive path
                # Classification must never break ingestion; we log and
                # continue with a payload that simply omits PII metadata.
                logger.warning("pii_classification_failed", error=str(exc))
            # Preserve optional metadata (including info_personal.id_cliente)
            if d.metadata:
                payload["metadata"] = d.metadata
            points.append(
                qmodels.PointStruct(id=pid, vector={"text": vec}, payload=payload)  # type: ignore[arg-type]
            )
        try:
            client.upsert(
                collection_name=settings.qdrant_collection_docs, points=points
            )
            total += len(points)
        except Exception as exc:  # pragma: no cover - defensive path
            logger.error("qdrant_upsert_failed", error=str(exc))
    logger.info("ingestion_completed", points=total)
    return total


def ingest_banking_corpus(jsonl_path: str | Path) -> int:
    """Ingest the full banking corpus from a JSONL file into Qdrant.

    Each line is expected to be a JSON object with at least a "texto" field and
    a nested "metadata.info_personal.id_cliente" structure. The full metadata
    object is preserved under the "metadata" key in the Qdrant payload so that
    access control can rely on metadata.info_personal.id_cliente.
    """

    path = Path(jsonl_path)
    docs: list[IngestDoc] = []
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("corpus_line_invalid_json", line_number=idx + 1)
                continue
            texto = obj.get("texto") or obj.get("text") or ""
            metadata = obj.get("metadata") or {}
            if not texto:
                continue
            # Build a stable doc_id using id_cliente when available, falling back
            # to the line index.
            info_personal = (
                metadata.get("info_personal", {}) if isinstance(metadata, dict) else {}
            )
            id_cliente = info_personal.get("id_cliente")
            doc_id = str(id_cliente or f"line-{idx + 1}")
            docs.append(
                IngestDoc(
                    doc_id=doc_id,
                    content=str(texto),
                    source="corpus_bancario",
                    metadata=metadata if isinstance(metadata, dict) else {},
                )
            )

    if not docs:
        logger.warning("corpus_bancario_empty_or_invalid", path=str(path))
        return 0

    logger.info("corpus_bancario_ingest_start", path=str(path), docs=len(docs))
    return upsert_documents(docs)


if __name__ == "__main__":  # pragma: no cover - script entry
    # Default to ingesting the banking corpus JSONL if present; otherwise fall
    # back to a small synthetic sample.
    default_corpus = Path("corpus_bancario_completo.jsonl")
    if default_corpus.exists():
        ingest_banking_corpus(default_corpus)
    else:
        sample = [
            IngestDoc(
                doc_id="demo-1",
                source="synthetic_policies",
                content=(
                    "Corporate policies define procedures for internal compliance. "
                    "Procedures outline step-by-step operational guidelines."
                ),
            )
        ]
        upsert_documents(sample)
