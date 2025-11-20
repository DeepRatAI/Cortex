from __future__ import annotations
from cortex_ka.application.prompt_builder import build_prompt


def test_prompt_truncates_when_budget_small():
    chunks = [f"chunk {i}" for i in range(50)]
    prompt = build_prompt("What?", chunks, budget_chars=300)
    assert "Question: What?" in prompt
    # Should not include all 50 chunks due to budget
    assert prompt.count("chunk") < 50


def test_prompt_includes_history():
    prompt = build_prompt(
        "What is policy?",
        ["A policy is an internal rule."],
        history=[("Old Q", "Old A")],
    )
    assert "Previous context" in prompt
    assert "Old Q" in prompt
    assert "A policy is an internal rule." in prompt
