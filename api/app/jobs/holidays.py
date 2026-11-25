"""The weekly bank-holiday import (plan.md T4.5)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from app.core.logging import get_logger
from app.integrations.govuk_bank_holidays import SOURCE_URL, FeedError, fetch
from app.modules.holidays.models import BankHoliday

if TYPE_CHECKING:
    import httpx
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger("app.jobs.holidays")


async def import_bank_holidays(
    engine: AsyncEngine, client: httpx.AsyncClient | None = None, *, today: date | None = None
) -> int:
    """Load every bank holiday in the feed; new ones are added and changed titles updated.

    The feed is the whole truth for the dates it covers (ISS-19): an upcoming date in a region,
    up to the last date the feed lists for it, that the feed no longer lists (a moved holiday)
    is removed. Past dates are history and stay. A feed that fails or is incomplete raises
    before anything is written, so the last good calendar is kept.

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
    start = today or now.date()
    async with engine.begin() as connection:
        await connection.execute(statement)
        for region in {h.region for h in holidays}:
            listed = {h.on_date for h in holidays if h.region == region}
            await connection.execute(
                delete(BankHoliday).where(
                    BankHoliday.region == region,
                    BankHoliday.on_date >= start,
                    BankHoliday.on_date <= max(listed),
                    BankHoliday.on_date.not_in(listed),
                )
            )
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
