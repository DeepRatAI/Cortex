from __future__ import annotations
from cortex_ka.infrastructure.memory_store import RateLimiter


def test_rate_limiter_allows_then_blocks():
    rl = RateLimiter(qpm=2)
    assert rl.allow() is True
    assert rl.allow() is True
    # third within same window should fail
    assert rl.allow() is False
