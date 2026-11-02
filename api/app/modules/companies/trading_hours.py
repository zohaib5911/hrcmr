"""Trading hours (plan.md 8.15): when the business is open on each weekday. Each day saves on its
own (``PUT /trading-hours/{weekday}``), which is what the page's per-row autosave calls."""

from __future__ import annotations

from datetime import time  # noqa: TC003  (Pydantic reads the annotations at run time)
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from app.core.schemas import RequestModel
from app.modules.companies.models import TradingHoursDay
from app.modules.rbac.deps import Access, require

router = APIRouter(tags=["company"])

Reads = Annotated[Access, Depends(require("company.profile.read"))]
Writes = Annotated[Access, Depends(require("company.profile.write"))]

Weekday = Annotated[int, Path(ge=1, le=7, description="1 is Monday, 7 is Sunday.")]


class TradingDay(BaseModel):
    weekday: int
    is_open: bool
    opens_at: time | None = None
    closes_at: time | None = None


class TradingHours(BaseModel):
    days: list[TradingDay] = Field(description="Monday to Sunday, always seven.")


class TradingDayIn(RequestModel):
    is_open: bool
    opens_at: time | None = None
    closes_at: time | None = None

    @model_validator(mode="after")
    def _times(self) -> TradingDayIn:
        if not self.is_open:
            # A closed day keeps no times, so reopening starts clean.
            self.opens_at = self.closes_at = None
            return self
        if self.opens_at is None or self.closes_at is None:
            raise ValueError("Say when it opens and when it closes.")
        if self.opens_at >= self.closes_at:
            raise ValueError("It must open before it closes.")
        return self


def _hhmm(value: time | None) -> str | None:
    return value.strftime("%H:%M") if value else None


def _json(day: TradingDay) -> dict[str, object]:
    return {
        "is_open": day.is_open,
        "opens_at": _hhmm(day.opens_at),
        "closes_at": _hhmm(day.closes_at),
    }


async def _current(access: Access) -> list[TradingDay]:
    rows = {
        row.weekday: row for row in (await access.db.execute(select(TradingHoursDay))).scalars()
    }
    return [
        TradingDay(
            weekday=d,
            is_open=rows[d].is_open,
            opens_at=rows[d].opens_at,
            closes_at=rows[d].closes_at,
        )
        if d in rows
        else TradingDay(weekday=d, is_open=False)
        for d in range(1, 8)
    ]


@router.get("/trading-hours", summary="When the business is open, day by day")
async def get_trading_hours(access: Reads) -> TradingHours:
    return TradingHours(days=await _current(access))


@router.put("/trading-hours/{weekday}", summary="Set one day's trading hours")
async def set_trading_day(weekday: Weekday, body: TradingDayIn, access: Writes) -> TradingDay:
    row = (
        await access.db.execute(select(TradingHoursDay).where(TradingHoursDay.weekday == weekday))
    ).scalar_one_or_none()
    before = next(d for d in await _current(access) if d.weekday == weekday)
    if row is None:
        row = TradingHoursDay(company_id=access.company_id, weekday=weekday)
        access.db.add(row)
    row.is_open, row.opens_at, row.closes_at = body.is_open, body.opens_at, body.closes_at
    await access.db.flush()
    after = TradingDay(
        weekday=weekday, is_open=body.is_open, opens_at=body.opens_at, closes_at=body.closes_at
    )
    if _json(before) != _json(after):
        await access.audit(
            "trading_hours.updated",
            entity_type="trading_hours",
            entity_id=access.company_id,
            before={"weekday": weekday, **_json(before)},
            after={"weekday": weekday, **_json(after)},
        )
    await access.db.commit()
    return after
