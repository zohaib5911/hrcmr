"""The working pattern and the holiday calendar (plan.md 8.6): ``/working-pattern`` and
``/holiday-management``, with the closures and holiday types that belong to it."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.core.errors import AppError, ConflictError, NotFoundError
from app.modules.companies.models import Company
from app.modules.holidays.models import (
    BankHoliday,
    CompanyHoliday,
    HolidayType,
    WorkingPatternDay,
)
from app.modules.holidays.schemas import (
    BankHolidayOut,
    CompanyHolidayIn,
    CompanyHolidayOut,
    CompanyHolidayPatch,
    HolidayManagement,
    HolidayTypeIn,
    HolidayTypeOut,
    PatternDay,
    WorkingPattern,
)
from app.modules.rbac.deps import Access, require

router = APIRouter(tags=["holidays"])

CalendarReads = Annotated[Access, Depends(require("holiday.calendar.read"))]
CalendarWrites = Annotated[Access, Depends(require("holiday.calendar.write"))]
TypeWrites = Annotated[Access, Depends(require("holiday.type.write"))]

# Until a company saves its own: Monday to Friday, eight hours a day.
DEFAULT_HOURS = Decimal("8.00")


# --- working pattern -----------------------------------------------------------------------------


def _pattern_json(days: list[PatternDay], bank: bool) -> dict[str, object]:
    return {
        "days": [
            {"weekday": d.weekday, "is_working": d.is_working, "hours": str(d.hours)} for d in days
        ],
        "bank_holidays_non_working": bank,
    }


async def _company(access: Access) -> Company:
    company = (
        await access.db.execute(select(Company).where(Company.id == access.company_id))
    ).scalar_one_or_none()
    if company is None:
        raise NotFoundError
    return company


async def _current_pattern(access: Access) -> WorkingPattern:
    rows = {
        row.weekday: row for row in (await access.db.execute(select(WorkingPatternDay))).scalars()
    }
    days = [
        PatternDay(weekday=d, is_working=rows[d].is_working, hours=rows[d].hours)
        if d in rows
        else PatternDay(
            weekday=d, is_working=d <= 5, hours=DEFAULT_HOURS if d <= 5 else Decimal("0")
        )
        for d in range(1, 8)
    ]
    return WorkingPattern(
        days=days, bank_holidays_non_working=(await _company(access)).bank_holidays_non_working
    )


@router.get("/working-pattern", summary="The company's normal working week")
async def get_working_pattern(access: CalendarReads) -> WorkingPattern:
    return await _current_pattern(access)


@router.put("/working-pattern", summary="Set the company's normal working week")
async def set_working_pattern(body: WorkingPattern, access: CalendarWrites) -> WorkingPattern:
    before = await _current_pattern(access)
    existing = {
        row.weekday: row for row in (await access.db.execute(select(WorkingPatternDay))).scalars()
    }
    for day in body.days:
        hours = day.hours if day.is_working else Decimal("0")
        row = existing.get(day.weekday)
        if row is None:
            access.db.add(
                WorkingPatternDay(
                    company_id=access.company_id,
                    weekday=day.weekday,
                    is_working=day.is_working,
                    hours=hours,
                )
            )
        else:
            row.is_working, row.hours = day.is_working, hours
    (await _company(access)).bank_holidays_non_working = body.bank_holidays_non_working
    await access.db.flush()
    after = await _current_pattern(access)
    if _pattern_json(before.days, before.bank_holidays_non_working) != _pattern_json(
        after.days, after.bank_holidays_non_working
    ):
        await access.audit(
            "working_pattern.updated",
            entity_type="working_pattern",
            entity_id=access.company_id,
            before=_pattern_json(before.days, before.bank_holidays_non_working),
            after=_pattern_json(after.days, after.bank_holidays_non_working),
        )
    await access.db.commit()
    return after


# --- holiday types -------------------------------------------------------------------------------


async def _type(access: Access, type_id: uuid.UUID) -> HolidayType:
    row = (
        await access.db.execute(
            select(HolidayType).where(HolidayType.id == type_id, HolidayType.archived_at.is_(None))
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return row


async def _name_taken(access: Access, name: str, except_id: uuid.UUID | None = None) -> bool:
    query = select(HolidayType.id).where(
        func.lower(HolidayType.name) == name.lower(), HolidayType.archived_at.is_(None)
    )
    if except_id:
        query = query.where(HolidayType.id != except_id)
    return (await access.db.execute(query)).first() is not None


@router.post("/holiday-types", status_code=201, summary="Add a holiday type")
async def add_type(body: HolidayTypeIn, access: TypeWrites) -> HolidayTypeOut:
    if await _name_taken(access, body.name):
        raise ConflictError("You already have a holiday type with that name.", field="name")
    row = HolidayType(company_id=access.company_id, name=body.name, colour=body.colour)
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "holiday_type.added",
        entity_type="holiday_type",
        entity_id=row.id,
        after={"name": row.name, "colour": row.colour},
    )
    await access.db.commit()
    return HolidayTypeOut(id=row.id, name=row.name, colour=row.colour)  # type: ignore[arg-type]


@router.patch("/holiday-types/{type_id}", summary="Rename or recolour a holiday type")
async def change_type(
    type_id: uuid.UUID, body: HolidayTypeIn, access: TypeWrites
) -> HolidayTypeOut:
    row = await _type(access, type_id)
    if await _name_taken(access, body.name, except_id=row.id):
        raise ConflictError("You already have a holiday type with that name.", field="name")
    before = {"name": row.name, "colour": row.colour}
    row.name, row.colour = body.name, body.colour
    after = {"name": row.name, "colour": row.colour}
    if before != after:
        await access.audit(
            "holiday_type.updated",
            entity_type="holiday_type",
            entity_id=row.id,
            before=before,
            after=after,
        )
    await access.db.commit()
    return HolidayTypeOut(id=row.id, name=row.name, colour=row.colour)


@router.delete("/holiday-types/{type_id}", status_code=204, summary="Archive a holiday type")
async def archive_type(type_id: uuid.UUID, access: TypeWrites) -> None:
    row = await _type(access, type_id)
    used = (
        await access.db.execute(
            select(func.count())
            .select_from(CompanyHoliday)
            .where(CompanyHoliday.holiday_type_id == row.id, CompanyHoliday.archived_at.is_(None))
        )
    ).scalar_one()
    if used:
        raise ConflictError("Change or remove the closures that use this type first.")
    row.archived_at = datetime.now(UTC)
    await access.audit(
        "holiday_type.archived", entity_type="holiday_type", entity_id=row.id, summary=row.name
    )
    await access.db.commit()


# --- company holidays ----------------------------------------------------------------------------


def _holiday_out(row: CompanyHoliday) -> CompanyHolidayOut:
    return CompanyHolidayOut(
        id=row.id,
        name=row.name,
        start_date=row.start_date,
        end_date=row.end_date,
        holiday_type_id=row.holiday_type_id,
        description=row.description,
        deduct_from_annual_leave=row.deduct_from_annual_leave,
    )


def _holiday_json(row: CompanyHoliday) -> dict[str, object]:
    return _holiday_out(row).model_dump(mode="json", exclude={"id"})


async def _holiday(access: Access, holiday_id: uuid.UUID) -> CompanyHoliday:
    row = (
        await access.db.execute(
            select(CompanyHoliday).where(
                CompanyHoliday.id == holiday_id, CompanyHoliday.archived_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return row


async def _check_type(access: Access, type_id: uuid.UUID | None) -> None:
    if type_id is not None:
        await _type(access, type_id)


@router.post("/company-holidays", status_code=201, summary="Add a closure")
async def add_holiday(body: CompanyHolidayIn, access: CalendarWrites) -> CompanyHolidayOut:
    await _check_type(access, body.holiday_type_id)
    row = CompanyHoliday(company_id=access.company_id, **body.model_dump())
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "company_holiday.added",
        entity_type="company_holiday",
        entity_id=row.id,
        after=_holiday_json(row),
    )
    await access.db.commit()
    return _holiday_out(row)


@router.patch("/company-holidays/{holiday_id}", summary="Change a closure")
async def change_holiday(
    holiday_id: uuid.UUID, body: CompanyHolidayPatch, access: CalendarWrites
) -> CompanyHolidayOut:
    row = await _holiday(access, holiday_id)
    before = _holiday_json(row)
    changes = body.model_dump(exclude_unset=True)
    for required in ("name", "start_date", "end_date"):
        if required in changes and changes[required] is None:
            raise AppError(
                "VALIDATION_ERROR", "That cannot be empty.", status_code=422, field=required
            )
    if changes.get("holiday_type_id") is not None:
        await _check_type(access, changes["holiday_type_id"])
    for name, value in changes.items():
        setattr(row, name, value)
    if row.end_date < row.start_date:
        raise AppError(
            "VALIDATION_ERROR",
            "The last day cannot be before the first day.",
            status_code=422,
            field="end_date",
        )
    after = _holiday_json(row)
    if before != after:
        await access.audit(
            "company_holiday.updated",
            entity_type="company_holiday",
            entity_id=row.id,
            before=before,
            after=after,
        )
    await access.db.commit()
    return _holiday_out(row)


@router.delete("/company-holidays/{holiday_id}", status_code=204, summary="Remove a closure")
async def remove_holiday(holiday_id: uuid.UUID, access: CalendarWrites) -> None:
    row = await _holiday(access, holiday_id)
    row.archived_at = datetime.now(UTC)
    await access.audit(
        "company_holiday.removed", entity_type="company_holiday", entity_id=row.id, summary=row.name
    )
    await access.db.commit()


# --- the page ------------------------------------------------------------------------------------


@router.get("/holiday-management", summary="Bank holidays, closures and holiday types for a year")
async def holiday_management(
    access: CalendarReads,
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
) -> HolidayManagement:
    company = await _company(access)
    chosen = year or datetime.now(ZoneInfo(company.timezone)).year
    first, last = date(chosen, 1, 1), date(chosen, 12, 31)
    bank = (
        (
            await access.db.execute(
                select(BankHoliday)
                .where(
                    BankHoliday.region == company.bank_holiday_region,
                    BankHoliday.on_date.between(first, last),
                )
                .order_by(BankHoliday.on_date)
            )
        )
        .scalars()
        .all()
    )
    fetched = (
        await access.db.execute(
            select(func.max(BankHoliday.fetched_at)).where(
                BankHoliday.region == company.bank_holiday_region
            )
        )
    ).scalar_one()
    closures = (
        (
            await access.db.execute(
                select(CompanyHoliday)
                .where(
                    CompanyHoliday.archived_at.is_(None),
                    CompanyHoliday.start_date <= last,
                    CompanyHoliday.end_date >= first,
                )
                .order_by(CompanyHoliday.start_date)
            )
        )
        .scalars()
        .all()
    )
    types = (
        (
            await access.db.execute(
                select(HolidayType)
                .where(HolidayType.archived_at.is_(None))
                .order_by(func.lower(HolidayType.name))
            )
        )
        .scalars()
        .all()
    )
    return HolidayManagement(
        year=chosen,
        region=company.bank_holiday_region,  # type: ignore[arg-type]
        bank_holidays=[BankHolidayOut(on_date=b.on_date, title=b.title) for b in bank],
        bank_holidays_updated_at=fetched,
        company_holidays=[_holiday_out(c) for c in closures],
        types=[HolidayTypeOut(id=t.id, name=t.name, colour=t.colour) for t in types],  # type: ignore[arg-type]
    )
