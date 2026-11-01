"""Redis client factory. Sessions, rate limits and the job queue all share one connection URL."""

from __future__ import annotations

from typing import TYPE_CHECKING

from redis.asyncio import Redis

if TYPE_CHECKING:
    from app.core.config import Settings


def create_redis(settings: Settings) -> Redis:
    return Redis.from_url(
        settings.redis_url.get_secret_value(),
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
        health_check_interval=30,
    )


async def ping_redis(client: Redis) -> None:
    """Raise if Redis does not answer."""
    if not await client.ping():
        raise ConnectionError("redis did not answer PING")
