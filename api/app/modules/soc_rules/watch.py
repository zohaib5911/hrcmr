"""The daily look at the GOV.UK rules pages (plan 8.17, T15.7).

It fetches the three pages the live rules came from. When their bytes have not changed, nothing
happens (the importer compares the page hashes and adds no draft). When they have changed, the pages
are parsed and a draft version is added for a platform admin to review. Nothing goes live here:
publishing is the admin's decision, and the parser refuses a page whose shape it does not know.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx
from sqlalchemy import select

from app.modules.soc_rules.importer import import_rules_source
from app.modules.soc_rules.models import RulesVersion
from app.modules.soc_rules.source import (
    PAGE_KINDS,
    page_from_bytes,
    rules_source_from_read,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

PAGE_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class WatchResult:
    status: str  # no_live_version | fetch_failed | parse_failed | unchanged | draft_created
    version_id: UUID | None = None
    detail: str = ""


async def watch_rules(
    db: AsyncSession, client: httpx.AsyncClient, today: dt.date | None = None
) -> WatchResult:
    """Fetches the live version's pages and adds a draft if they changed. The caller commits."""
    live = (
        await db.execute(select(RulesVersion).where(RulesVersion.status == "live"))
    ).scalar_one_or_none()
    if live is None:
        return WatchResult(
            "no_live_version",
            detail="No rules version is live yet. Import and publish the first one first.",
        )
    urls = {str(page["kind"]): str(page["url"]) for page in live.source_urls}
    if sorted(urls) != sorted(PAGE_KINDS):
        return WatchResult("fetch_failed", detail="The live version does not list all three pages.")
    retrieved = (today or dt.datetime.now(dt.UTC).date()).isoformat()
    read = {}
    for kind in PAGE_KINDS:
        try:
            response = await client.get(urls[kind], timeout=PAGE_TIMEOUT_SECONDS)
            response.raise_for_status()
        except httpx.HTTPError:
            return WatchResult("fetch_failed", detail=f"Could not fetch the {kind} page.")
        read[kind] = page_from_bytes(kind, urls[kind], response.content, retrieved)
    try:
        source = rules_source_from_read(read)
    except ValueError as exc:
        # The pages changed in a way the parser does not know: a person must look before any draft.
        return WatchResult("parse_failed", detail=str(exc))
    result = await import_rules_source(db, source)
    if result.unchanged or result.version_id is None:
        return WatchResult("unchanged")
    return WatchResult(
        "draft_created",
        version_id=result.version_id,
        detail=f"Draft added with {sum(result.counts.values())} rows; review it before publishing.",
    )
