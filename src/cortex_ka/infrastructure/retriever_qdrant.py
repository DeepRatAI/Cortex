"""Qdrant retriever adapter using local embeddings and query_points API.

Provides semantic similarity search against a named collection. Falls back gracefully
to an empty result if the service is unreachable or collection absent. Uses a single
named vector "text"; multi-vector or metadata filtering can be incorporated later.
"""

from __future__ import annotations
from typing import List, Any, Dict
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from ..domain.ports import RetrieverPort
from ..domain.models import DocumentChunk, RetrievalResult
from ..config import settings
from .embedding_local import LocalEmbedder
from ..logging import logger


class QdrantRetriever(RetrieverPort):
    """Retrieve document chunks from Qdrant by semantic similarity.

    Args:
        collection: Name of Qdrant collection containing document vectors.
        top_k: Default max results to return when k not specified.
    """

    def __init__(self, collection: str | None = None, top_k: int | None = None) -> None:
        self._collection = collection or settings.qdrant_collection_docs
        self._top_k = top_k or settings.qdrant_top_k
        self._client = QdrantClient(
            url=settings.qdrant_url, api_key=settings.qdrant_api_key or None, timeout=5
        )
        self._embedder = LocalEmbedder()

    def retrieve(
        self, query: str, k: int | None = None, subject_id: str | None = None
    ) -> RetrievalResult:  # type: ignore[override]
        k = k or self._top_k
        try:
            vector: List[float] = self._embedder.embed([query])[0]
            # Build filter for subject_id using Qdrant's Filter/FieldCondition model
            q_filter = None
            if subject_id:
                q_filter = qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="metadata.info_personal.id_cliente",
                            match=qmodels.MatchValue(value=subject_id),
                        )
                    ]
                )

            # Use search API compatible with current qdrant-client instead of
            # query_points which is not available in your version.
            hits = self._client.search(
                collection_name=self._collection,
                query_vector=("text", vector),
                limit=k,
                query_filter=q_filter,
                with_payload=True,
            )
            chunks: list[DocumentChunk] = []
            for h in hits:
                payload: Dict[str, Any] = getattr(h, "payload", {}) or {}

                # Optional enforcement: skip chunks explicitly marked as
                # high-sensitivity PII. This relies on the ingestion pipeline
                # populating payload["pii"]["sensitivity"] using
                # `classify_pii`. We do this unconditionally here because the
                # classifier is lightweight and deterministic, and banking
                # contexts generally prefer to err on the side of caution.
                pii_info = payload.get("pii") or {}
                if isinstance(pii_info, dict) and pii_info.get("sensitivity") == "high":
                    continue
                # Normalize possible payload key variations
                text = (
                    payload.get("text")
                    or payload.get("chunk")
                    or payload.get("content")
                    or ""
                )
                source = (
                    payload.get("source")
                    or payload.get("doc")
                    or payload.get("document")
                    or "unknown"
                )
                pii_info = payload.get("pii") or {}
                pii_sensitivity = None
                if isinstance(pii_info, dict):
                    val = pii_info.get("sensitivity")
                    if isinstance(val, str):
                        pii_sensitivity = val
                if text:
                    chunks.append(
                        DocumentChunk(
                            id=str(getattr(h, "id", "")),
                            text=str(text),
                            source=str(source),
                            pii_sensitivity=pii_sensitivity,
                        )
                    )
            return RetrievalResult(query=query, chunks=chunks)
        except Exception as exc:  # pragma: no cover - defensive path
            logger.warning("qdrant_retrieval_failed", error=str(exc))
            return RetrievalResult(query=query, chunks=[])
