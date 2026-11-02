"""Cloudflare's address lists: parsing, refusing a bad reply, and the weekly job (no network)."""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.client_ip import CLOUDFLARE_RANGES, cloudflare_ranges, use_cloudflare_ranges
from app.integrations.cloudflare_ips import (
    REDIS_KEY,
    RangesError,
    check,
    fetch,
    load_saved_ranges,
    parse,
)
from app.jobs.cloudflare import cloudflare_ranges_weekly

V4 = "\n".join(f"10.{n}.0.0/16" for n in range(6))
V6 = "2400:cb00::/32\n2606:4700::/32\n"


def _client(v4: str = V4, v6: str = V6, status: int = 200) -> httpx.AsyncClient:
    def answer(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=v6 if request.url.path.endswith("v6") else v4)

    return httpx.AsyncClient(transport=httpx.MockTransport(answer))


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.data[key] = value

    async def get(self, key: str) -> str | None:
        return self.data.get(key)


def test_parse_reads_networks_and_refuses_anything_else() -> None:
    assert parse("1.1.1.0/24\n\n2400:cb00::/32\n") == ["1.1.1.0/24", "2400:cb00::/32"]
    with pytest.raises(RangesError):
        parse("<html>Access denied</html>")
    with pytest.raises(RangesError):
        check(["1.1.1.0/24"])


async def test_the_job_saves_the_list_and_the_api_reads_it() -> None:
    redis = FakeRedis()
    try:
        assert await cloudflare_ranges_weekly({"redis": redis, "http": _client()}) == 8
        assert len(json.loads(redis.data[REDIS_KEY])) == 8
        await load_saved_ranges(redis)  # type: ignore[arg-type]
        assert len(cloudflare_ranges()) == 8
    finally:
        use_cloudflare_ranges(None)
    assert cloudflare_ranges() == CLOUDFLARE_RANGES


async def test_a_bad_reply_leaves_everything_as_it_was() -> None:
    redis = FakeRedis()
    assert await cloudflare_ranges_weekly({"redis": redis, "http": _client(status=503)}) == 0
    assert await cloudflare_ranges_weekly({"redis": redis, "http": _client(v4="oops")}) == 0
    assert REDIS_KEY not in redis.data
    with pytest.raises(RangesError):
        await fetch(_client(v6=""))
