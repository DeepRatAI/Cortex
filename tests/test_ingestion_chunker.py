from __future__ import annotations
from cortex_ka.scripts.ingest_docs import simple_chunks


def test_simple_chunks_splits_reasonably():
    text = " ".join(["word"] * 120)  # ~480 chars + spaces
    chunks = simple_chunks(text, max_len=200)
    assert len(chunks) >= 2
    assert all(isinstance(c, str) and len(c) > 0 for c in chunks)
