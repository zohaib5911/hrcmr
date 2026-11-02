"""The weekly bank-holiday import (plan.md T4.5)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.dialects.postgresql import insert

from app.core.logging import get_logger
from app.integrations.govuk_bank_holidays import SOURCE_URL, FeedError, fetch
from app.modules.holidays.models import BankHoliday

if TYPE_CHECKING:
    import httpx
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger("app.jobs.holidays")


async def import_bank_holidays(engine: AsyncEngine, client: httpx.AsyncClient | None = None) -> int:
    """Load every bank holiday in the feed; new ones are added and changed titles updated.

    Runs as the table owner. Returns how many dates the feed listed."""
    holidays = await fetch(client)
    if not holidays:
        return 0
    now = datetime.now(UTC)
    rows = [
        {
            "region": h.region,
            "on_date": h.on_date,
            "title": h.title,
            "source": SOURCE_URL,
            "fetched_at": now,
        }
        for h in holidays
    ]
    statement = insert(BankHoliday).values(rows)
    statement = statement.on_conflict_do_update(
        constraint="uq_bank_holidays_region_on_date",
        set_={"title": statement.excluded.title, "fetched_at": now, "source": SOURCE_URL},
    )
    async with engine.begin() as connection:
        await connection.execute(statement)
    logger.info("bank_holidays_imported", count=len(rows))
    return len(rows)


async def bank_holidays_weekly(ctx: dict[str, Any]) -> int:
    """The scheduled job. With no owner connection, or a feed that is down, it does nothing."""
    engine = ctx.get("owner_engine")
    if engine is None:
        return 0
    try:
        return await import_bank_holidays(engine, ctx.get("http"))
    except FeedError:
        return 0
