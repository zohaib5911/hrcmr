"""The fixed-window limiter: counting, refusing, and never leaving a counter without an expiry."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from redis.asyncio import Redis

from app.core.rate_limit import RateLimiter, hashed
from tests.support import TEST_REDIS_URL


@pytest.fixture
async def redis(stack: None) -> AsyncIterator[Redis]:
    client = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


async def test_it_counts_refuses_past_the_limit_and_says_when_to_retry(redis: Redis) -> None:
    limiter = RateLimiter(redis)
    results = [await limiter.hit("t", "someone", limit=2, window_seconds=60) for _ in range(3)]
    assert [r.allowed for r in results] == [True, True, False]
    assert [r.remaining for r in results] == [1, 0, 0]
    assert 0 < results[-1].retry_after <= 60
    await limiter.reset("t", "someone")
    assert (await limiter.hit("t", "someone", limit=2, window_seconds=60)).allowed


async def test_a_counter_without_an_expiry_is_given_one(redis: Redis) -> None:
    """C6.1.4: a counter left with no expiry used to refuse its subject for ever."""
    key = f"rl:t:{hashed('someone')}"
    await redis.set(key, 99)  # what the old two-step limiter could leave behind
    assert await redis.ttl(key) == -1
    result = await RateLimiter(redis).hit("t", "someone", limit=5, window_seconds=60)
    assert not result.allowed
    assert 0 < await redis.ttl(key) <= 60
    assert 0 < result.retry_after <= 60


async def test_a_new_window_always_has_an_expiry(redis: Redis) -> None:
    await RateLimiter(redis).hit("t", "fresh", limit=5, window_seconds=30)
    assert 0 < await redis.ttl(f"rl:t:{hashed('fresh')}") <= 30


class _ZeroTtl:
    """Redis answering as it does with under a second left in the window."""

    def __init__(self, ttl: int) -> None:
        self.ttl = ttl

    async def eval(self, *_args: object) -> list[int]:
        return [11, self.ttl]


async def test_a_window_about_to_end_asks_for_one_second_not_a_new_hour() -> None:
    """ISS-23: TTL 0 on the hourly limit means retry in one second."""
    result = await RateLimiter(_ZeroTtl(0)).hit(  # type: ignore[arg-type]
        "login-account", "someone", limit=10, window_seconds=3600
    )
    assert not result.allowed
    assert result.retry_after == 1
    missing = await RateLimiter(_ZeroTtl(-1)).hit(  # type: ignore[arg-type]
        "login-account", "someone", limit=10, window_seconds=3600
    )
    assert missing.retry_after == 3600
