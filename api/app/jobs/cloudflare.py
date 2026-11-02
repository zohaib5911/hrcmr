"""The weekly refresh of Cloudflare's address ranges (see core/client_ip.py)."""

from __future__ import annotations

import json
from typing import Any

from app.core.logging import get_logger
from app.integrations.cloudflare_ips import REDIS_KEY, REDIS_TTL_SECONDS, RangesError, fetch

logger = get_logger("app.jobs.cloudflare")


async def cloudflare_ranges_weekly(ctx: dict[str, Any]) -> int:
    """Save the current list in Redis for the API. If Cloudflare does not answer properly the saved
    list (or the one built into the code) stays in use. Returns how many ranges were saved."""
    redis = ctx.get("redis")
    if redis is None:
        return 0
    try:
        ranges = await fetch(ctx.get("http"))
    except RangesError:
        return 0
    await redis.set(REDIS_KEY, json.dumps(ranges), ex=REDIS_TTL_SECONDS)
    logger.info("cloudflare_ranges_saved", count=len(ranges))
    return len(ranges)
