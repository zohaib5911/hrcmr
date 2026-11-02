"""The job queue (ARQ on Redis): how the API asks the worker to do something later."""

from __future__ import annotations

from typing import TYPE_CHECKING

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

if TYPE_CHECKING:
    from app.core.config import Settings


class ArqQueue:
    def __init__(self, pool: ArqRedis) -> None:
        self._pool = pool

    async def enqueue(self, function: str, *args: str, job_id: str) -> None:
        await self._pool.enqueue_job(function, *args, _job_id=job_id)

    async def close(self) -> None:
        await self._pool.aclose()


def redis_settings(settings: Settings) -> RedisSettings:
    return RedisSettings.from_dsn(settings.redis_url.get_secret_value())


async def open_queue(settings: Settings) -> ArqQueue:
    return ArqQueue(await create_pool(redis_settings(settings)))
