from __future__ import annotations
from cortex_ka.application.rag_service import RAGService
from cortex_ka.domain.ports import RetrieverPort, LLMPort, CachePort
from cortex_ka.domain.models import RetrievalResult, DocumentChunk


class DummyRetriever(RetrieverPort):
    def retrieve(
        self, query: str, k: int = 5, subject_id: str | None = None
    ) -> RetrievalResult:  # type: ignore[override]
        return RetrievalResult(
            query=query,
            chunks=[
                DocumentChunk(
                    id="1", text="A policy describes internal rules.", source="synth"
                )
            ],
        )


class DummyLLM(LLMPort):
    def generate(self, prompt: str) -> str:  # type: ignore[override]
        assert "A policy describes" in prompt
        return "Policies are internal rules."


class DummyCache(CachePort):
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get_answer(self, query: str) -> str | None:
        return self._store.get(query)

    def set_answer(self, query: str, answer: str) -> None:
        self._store[query] = answer


def test_rag_service_answer_generates_and_caches():
    service = RAGService(DummyRetriever(), DummyLLM(), DummyCache())

    a1 = service.answer("What is a policy?")
    assert "Policies" in a1.answer
    assert a1.used_chunks == ["1"]

    # second call should hit cache
    a2 = service.answer("What is a policy?")
    assert a2.answer == a1.answer


class RecordingCache(CachePort):
    """Cache double that records keys to verify scoping by subject_id + query."""

    def __init__(self) -> None:
        self.get_keys: list[str] = []
        self.set_keys: list[str] = []
        self._store: dict[str, str] = {}

    def get_answer(self, key: str) -> str | None:  # type: ignore[override]
        self.get_keys.append(key)
        return self._store.get(key)

    def set_answer(self, key: str, answer: str) -> None:  # type: ignore[override]
        self.set_keys.append(key)
        self._store[key] = answer


def test_rag_service_cache_scoped_by_subject_and_query():
    """Cache keys must distinguish at least subject_id and query.

    Two different subjects issuing the same query should not share cached
    responses, preventing cross-tenant cache poisoning.
    """

    cache = RecordingCache()
    service = RAGService(DummyRetriever(), DummyLLM(), cache)

    # First subject asks a question
    service.answer("What is a policy?", subject_id="subject-A")
    # Second subject asks the same question
    service.answer("What is a policy?", subject_id="subject-B")

    # We expect at least two distinct cache keys for the two subjects.
    # The concrete format includes the regulatory_strict flag, but the
    # important invariant is that different subjects do not share cache
    # entries for the same query.
    assert len(set(cache.set_keys)) >= 2


class EmptyRetriever(RetrieverPort):
    def retrieve(
        self, query: str, k: int = 5, subject_id: str | None = None
    ) -> RetrievalResult:  # type: ignore[override]
        return RetrievalResult(query=query, chunks=[])


def test_rag_service_regulatory_strict_avoids_hallucination_when_no_context():
    """In regulatory_strict mode, no context should mean no LLM call.

    Instead, the service must return a conservative, non-hallucinated answer
    instructing the user to consult official banking policies.
    """

    class RecordingLLM(LLMPort):
        def __init__(self) -> None:
            self.calls: list[str] = []

        def generate(self, prompt: str) -> str:  # type: ignore[override]
            self.calls.append(prompt)
            return "SHOULD NOT BE USED IN STRICT MODE WITHOUT CONTEXT"

    cache = DummyCache()
    llm = RecordingLLM()
    service = RAGService(EmptyRetriever(), llm, cache)

    answer = service.answer("¿Cuál es la tasa regulatoria?", regulatory_strict=True)

    # No retrieval context -> we expect a safe, canned message and no LLM calls.
    assert "No se encontraron documentos de soporte" in answer.answer
    assert answer.used_chunks == []
    assert answer.citations == []
    assert llm.calls == []
