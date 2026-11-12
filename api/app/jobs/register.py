"""Twice per UK working day, with UTC candidates covering GMT and BST."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.holidays.models import BankHoliday
from app.modules.register.geo import geocode_from_latest_dataset
from app.modules.register.ingest import ingest


async def register_ingest(ctx: dict[str, Any]) -> str:
    now = ctx.get("now", datetime.now(UTC)).astimezone(ZoneInfo("Europe/London"))
    if now.weekday() >= 5 or now.hour not in (10, 16):
        return "outside_schedule"
    return await _import(ctx, now, scheduled=True)


async def register_ingest_manual(ctx: dict[str, Any]) -> str:
    """Admin reruns use the same atomic ingest, without the cron calendar gate."""
    now = ctx.get("now", datetime.now(UTC)).astimezone(ZoneInfo("Europe/London"))
    return await _import(ctx, now, scheduled=False)


async def _import(ctx: dict[str, Any], now: datetime, *, scheduled: bool) -> str:
    engine = ctx.get("owner_engine")
    if engine is None:
        return "no_owner_engine"
    async with AsyncSession(engine) as db:
        if scheduled and await db.scalar(
            select(BankHoliday.id).where(
                BankHoliday.region == "england-and-wales", BankHoliday.on_date == now.date()
            )
        ):
            return "bank_holiday"
        async with httpx.AsyncClient(timeout=60) as client:
            result = await ingest(db, ctx.get("http", client), now.date())
        if result == "imported":
            await geocode_from_latest_dataset(db)
        await db.commit()
        return result
