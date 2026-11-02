"""Cloudflare's published address ranges (the lists at cloudflare.com/ips-v4 and /ips-v6).

Fetched by the weekly job and shared with the API through Redis, so the list of networks whose
``CF-Connecting-IP`` header is believed stays current. Only those two fixed addresses are called. A
reply that does not look like the list (empty, too short, not addresses) is refused, and the list
built into ``core/client_ip.py`` stays in use.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
from typing import TYPE_CHECKING

import httpx
from redis.exceptions import RedisError

from app.core.client_ip import use_cloudflare_ranges
from app.core.logging import get_logger

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = get_logger("app.cloudflare_ips")

SOURCES = ("https://www.cloudflare.com/ips-v4", "https://www.cloudflare.com/ips-v6")
TIMEOUT_SECONDS = 15.0
# Cloudflare lists about 15 IPv4 and 7 IPv6 ranges; far fewer means the reply is not the list.
MIN_V4, MIN_V6 = 5, 2
# Where the worker leaves the list for the API.
REDIS_KEY = "cloudflare:ip-ranges"
REDIS_TTL_SECONDS = 60 * 60 * 24 * 30


class RangesError(Exception):
    """The ranges could not be fetched or were not what they should be."""


def parse(text: str) -> list[str]:
    """One network per line; anything else is an error."""
    found: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            found.append(str(ipaddress.ip_network(line)))
        except ValueError as exc:
            raise RangesError("a line was not a network") from exc
    return found


def check(ranges: list[str]) -> list[str]:
    v4 = sum(1 for r in ranges if ":" not in r)
    if v4 < MIN_V4 or len(ranges) - v4 < MIN_V6:
        raise RangesError("the list is shorter than Cloudflare's")
    return ranges


async def fetch(client: httpx.AsyncClient | None = None) -> list[str]:
    own = client is None
    http = client or httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=False)
    try:
        ranges: list[str] = []
        for url in SOURCES:
            response = await http.get(url, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
            ranges.extend(parse(response.content.decode("utf-8", errors="replace")))
        return check(ranges)
    except httpx.HTTPError as exc:
        logger.warning("cloudflare_ranges_unavailable", kind=type(exc).__name__)
        raise RangesError("cloudflare did not answer") from exc
    finally:
        if own:
            await http.aclose()


REFRESH_SECONDS = 3600


async def load_saved_ranges(redis: Redis) -> None:
    """Use the list the worker saved; if Redis has none (or is down) keep what is in use."""
    try:
        saved = await redis.get(REDIS_KEY)
        if saved:
            use_cloudflare_ranges(check([str(item) for item in json.loads(saved)]))
    except (RedisError, RangesError, ValueError, TypeError):
        logger.warning("cloudflare_ranges_not_loaded")


async def keep_cloudflare_ranges_current(redis: Redis) -> None:
    """Runs for the life of the API: read the saved list now and every hour."""
    while True:
        await load_saved_ranges(redis)
        await asyncio.sleep(REFRESH_SECONDS)
