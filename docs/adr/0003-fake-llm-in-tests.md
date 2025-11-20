# ADR 0003: Fake LLM in Tests

Context: Unit tests should not depend on network access or external LLM availability.

Decision: Introduce `_FakeLLM` used automatically when `PYTEST_CURRENT_TEST` or `CKA_FAKE_LLM` flag is set.

Consequences:

- Deterministic responses enable simple assertions.
- Avoids flakiness from network or model runtime.
- Requires integration tests (future) to explicitly disable flag for end-to-end validation.
