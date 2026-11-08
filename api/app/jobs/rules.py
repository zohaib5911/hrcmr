"""The daily GOV.UK rules watch (T15.7, R3). The worker registers it in ``scheduled.py``.

It runs with the table owner's connection, because it adds a draft rules version. Running it
twice in a day is safe: an unchanged page adds nothing.
"""

from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.soc_rules.watch import watch_rules

logger = get_logger("app.jobs.rules")


async def rules_watch_daily(ctx: dict[str, Any]) -> str:
    owner = ctx.get("owner_engine")
    if owner is None:
        return "no_owner_engine"
    async with httpx.AsyncClient(follow_redirects=True) as client, AsyncSession(owner) as db:
        result = await watch_rules(db, client)
        await db.commit()
    logger.info("rules_watch", status=result.status, version_id=str(result.version_id or ""))
    return result.status
