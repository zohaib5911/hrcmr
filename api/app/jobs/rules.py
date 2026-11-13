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

# GOV.UK may redirect between its own pages; a hop to any other host is refused (T21.4, SSRF).
ALLOWED_HOSTS = frozenset({"www.gov.uk"})


class RefusedHostError(httpx.RequestError):
    """An HTTPError, so the watch reports ``fetch_failed`` instead of crashing the job."""


async def refuse_other_hosts(request: httpx.Request) -> None:
    """A request hook: httpx runs it for the first request and for every redirect it follows."""
    if request.url.scheme != "https" or request.url.host not in ALLOWED_HOSTS:
        raise RefusedHostError(f"Refused a request to {request.url.host!r}", request=request)


def watch_client(transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=transport,
        follow_redirects=True,
        max_redirects=5,
        event_hooks={"request": [refuse_other_hosts]},
    )


async def rules_watch_daily(ctx: dict[str, Any]) -> str:
    owner = ctx.get("owner_engine")
    if owner is None:
        return "no_owner_engine"
    async with watch_client() as client, AsyncSession(owner) as db:
        result = await watch_rules(db, client)
        await db.commit()
    logger.info("rules_watch", status=result.status, version_id=str(result.version_id or ""))
    return result.status
