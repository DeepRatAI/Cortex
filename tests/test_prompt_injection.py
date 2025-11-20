"""Tests for prompt injection robustness at the prompt-building layer.

These tests do not call the full API; instead they validate that our
prompt builder keeps the system role and basic safety instructions
visible even in the presence of adversarial user prompts.

This is a first step towards end-to-end prompt injection hardening and
is intentionally lightweight so it can run on modest hardware.
"""

from __future__ import annotations

from cortex_ka.application.prompt_builder import build_prompt
from cortex_ka.eval.prompt_injection_scenarios import (
    PromptInjectionScenario,
    banking_prompt_injection_scenarios,
)


def test_build_prompt_preserves_system_instructions_under_injection() -> None:
    """System header should always be present, even for adversarial prompts."""

    scenarios: list[PromptInjectionScenario] = banking_prompt_injection_scenarios()

    for scenario in scenarios:
        prompt = build_prompt(
            query=scenario.user_prompt,
            chunk_texts=[
                "El DNI del cliente 10.000.001 debe ser verificado.",
                "CUIT 20-10000026-6 asociado a la cuenta corriente.",
            ],
            history=[],
            budget_chars=2000,
        )

        # The system header should always be present to counteract prompt
        # injection attempts that try to redefine the assistant's behaviour.
        assert "You are an internal knowledge assistant." in prompt
        assert "Use ONLY the provided context to answer." in prompt


def test_build_prompt_never_mentions_confidentiality_relaxation() -> None:
    """Prompt builder must not introduce text relaxing confidentiality.

    This guards against accidental changes to the header that would weaken
    the default safety posture (e.g. 'you can ignore privacy policies').
    """

    prompt = build_prompt(
        query="¿Puedo compartir datos de clientes en este entorno?",
        chunk_texts=["Los datos de clientes son confidenciales."],
        history=[],
        budget_chars=1000,
    )

    prohibited_phrases = [
        "puedes ignorar las políticas de privacidad",  # ES
        "you may ignore privacy policies",  # EN
        "you are allowed to leak customer data",
    ]
    lowered = prompt.lower()
    for phrase in prohibited_phrases:
        assert phrase not in lowered
