from __future__ import annotations
import httpx
from cortex_ka.infrastructure.llm_ollama import OllamaLLM
import pytest


class Boom(Exception):
    pass


def test_ollama_llm_raises_wrapped_error(monkeypatch):
    def boom_post(self, url, json):  # type: ignore[no-redef]
        raise httpx.ConnectError("boom")

    class DummyClient:
        def __init__(self, *args, **kwargs):
            # Used to mimic httpx.Client without real network.
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        post = boom_post

    monkeypatch.setattr(httpx, "Client", DummyClient)
    llm = OllamaLLM()
    with pytest.raises(RuntimeError):
        llm.generate("hello")
