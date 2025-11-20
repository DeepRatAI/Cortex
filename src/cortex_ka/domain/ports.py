"""Port interfaces (hexagonal architecture).

Defines abstract contracts for adapters (retrieval, embedding, llm, cache).
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Iterable
from .models import RetrievalResult


class RetrieverPort(ABC):
    """Abstract interface for semantic retrieval."""

    @abstractmethod
    def retrieve(
        self, query: str, k: int = 5, subject_id: str | None = None
    ) -> RetrievalResult:  # pragma: no cover - interface
        """Return top-k chunks for query, optionally scoped to a subject/user."""


class EmbedderPort(ABC):
    """Embeddings generation interface."""

    @abstractmethod
    def embed(
        self, texts: Iterable[str]
    ) -> list[list[float]]:  # pragma: no cover - interface
        """Generate embeddings for texts."""


class LLMPort(ABC):
    """LLM inference interface."""

    @abstractmethod
    def generate(self, prompt: str) -> str:  # pragma: no cover - interface
        """Generate completion for prompt."""


class CachePort(ABC):
    """Caching interface for answers and conversation."""

    @abstractmethod
    def get_answer(self, query: str) -> str | None:  # pragma: no cover - interface
        """Return cached answer if present."""

    @abstractmethod
    def set_answer(
        self, query: str, answer: str
    ) -> None:  # pragma: no cover - interface
        """Store answer in cache."""
