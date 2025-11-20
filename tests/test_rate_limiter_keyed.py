from __future__ import annotations
from cortex_ka.infrastructure.memory_store import RateLimiter


def test_rate_limiter_keyed_buckets_independent():
    rl = RateLimiter(qpm=2)
    # Use key A fully
    assert rl.allow(key="A") is True
    assert rl.allow(key="A") is True
    # Third for A should fail
    assert rl.allow(key="A") is False
    # But key B should still have its own budget
    assert rl.allow(key="B") is True
    assert rl.allow(key="B") is True
    assert rl.allow(key="B") is False
