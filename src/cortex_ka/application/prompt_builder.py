"""Prompt builder for RAG generation.

Encapsulates construction of prompts from retrieved chunks and optional
conversation history. Applies a simple character budget to avoid oversizing
the context window.
"""

from __future__ import annotations
from typing import Iterable, Sequence, Tuple


def build_prompt(
    query: str,
    chunk_texts: Sequence[str],
    history: Iterable[Tuple[str, str]] | None = None,
    budget_chars: int = 4000,
) -> str:
    """Assemble a concise, professional prompt.

    Args:
        query: The current user question.
        chunk_texts: Context chunks ordered by relevance.
        history: Optional list of previous (user, assistant) tuples.
        budget_chars: Maximum characters allowed for the final prompt.
    Returns:
        Prompt string ready for the LLM.
    """
    header = "You are an internal knowledge assistant. Use ONLY the provided context to answer.\n\n"
    hist = ""
    if history:
        joined = "\n".join(f"- Q: {q}\n- A: {a}" for q, a in history)
        hist = f"Previous context (most recent first):\n{joined}\n\n"

    bullet_chunks: list[str] = []
    used = 0
    for t in chunk_texts:
        bullet = f"- {t}"
        if (
            used + len(bullet) + len(header) + len(hist) + len(query) + 64
            > budget_chars
        ):
            break
        bullet_chunks.append(bullet)
        used += len(bullet)

    body = "\n\n".join(bullet_chunks)
    ending = f"\n\nQuestion: {query}\nAnswer in concise professional language."
    return header + hist + body + ending
