"""Atomic copy/clear actions; only the writer's permitted employees are changed."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from sqlalchemy import select

from app.core.errors import AppError, NotFoundError
from app.modules.attendance.router import _company
from app.modules.employees.models import Employee
from app.modules.rota.week_router import Writes  # noqa: TC001
from app.modules.rota.week_schemas import (
    ActionOut,
    ClearWeek,
    CopyDay,
    EmployeeWeekAction,
    ShiftIn,
    WeekVersion,
)
from app.modules.rota.weeks import lock_week, monday, rows, save, touch, write_ids

if TYPE_CHECKING:
    from app.modules.rbac.deps import Access
    from app.modules.rota.week_models import RotaWeek, ScheduledShift

router = APIRouter(prefix="/rota/weeks", tags=["rota"])


async def _employee(access: Access, ident: uuid.UUID) -> None:
    if (
        not await access.can_reach(ident)
        or (await access.db.execute(select(Employee.id).where(Employee.id == ident))).first()
        is None
    ):
        raise NotFoundError


async def _replace(
    access: Access,
    week: RotaWeek,
    source: list[tuple[ScheduledShift, date]],
    target: list[ScheduledShift],
) -> ActionOut:
    # Capture local values before deleting: source may be a shift in the target week.
    zone = ZoneInfo((await _company(access)).timezone)
    incoming = [
        ShiftIn(
            version=week.version,
            employee_id=r.employee_id,
            date=day,
            starts_at=r.starts_at.astimezone(zone).time().replace(tzinfo=None),
            ends_at=r.ends_at.astimezone(zone).time().replace(tzinfo=None),
            unpaid_break_minutes=r.unpaid_break_minutes,
            shift_type_id=r.shift_type_id,
            note=r.note,
        )
        for r, day in source
    ]
    # Serialize with leave approval, preserving the common ascending employee lock order.
    ids = {r.employee_id for r in target} | {r.employee_id for r, _ in source}
    await access.db.execute(
        select(Employee.id).where(Employee.id.in_(ids)).order_by(Employee.id).with_for_update()
    )
    for row in target:
        await access.db.delete(row)
    await access.db.flush()
    for body in incoming:
        await save(access, week, body)
    if incoming or target:
        touch(week)
        await access.audit(
            "rota.week_action",
            after={
                "week_start": week.week_start.isoformat(),
                "removed": len(target),
                "created": len(incoming),
            },
        )
    await access.db.commit()
    return ActionOut(count=len(incoming) if incoming else len(target), version=week.version)


@router.post("/{week_start}/clear", response_model=ActionOut)
async def clear(week_start: date, body: ClearWeek, access: Writes) -> ActionOut:
    week = await lock_week(access, week_start, body.version)
    if body.on is not None and monday(body.on) != week_start:
        raise AppError("VALIDATION_ERROR", "Choose a day in this week.", status_code=422)
    selected = await rows(access, week_start, await write_ids(access))
    target = [r for r, _, _ in selected if body.on is None or r.date == body.on]
    return await _replace(access, week, [], target)


@router.post("/{week_start}/clear-employee-week", response_model=ActionOut)
async def clear_employee(week_start: date, body: EmployeeWeekAction, access: Writes) -> ActionOut:
    await _employee(access, body.employee_id)
    week = await lock_week(access, week_start, body.version)
    target = [r for r, _, _ in await rows(access, week_start, [body.employee_id])]
    return await _replace(access, week, [], target)


async def _copy_week(
    access: Access, week_start: date, version: int, employee_id: uuid.UUID | None = None
) -> ActionOut:
    if employee_id is not None:
        await _employee(access, employee_id)
    week = await lock_week(access, week_start, version)
    ids = [employee_id] if employee_id is not None else await write_ids(access)
    try:
        previous = week_start - timedelta(days=7)
    except OverflowError as error:
        raise AppError(
            "VALIDATION_ERROR", "There is no previous week for this date.", status_code=422
        ) from error
    source = [(r, r.date + timedelta(days=7)) for r, _, _ in await rows(access, previous, ids)]
    target = [r for r, _, _ in await rows(access, week_start, ids)]
    return await _replace(access, week, source, target)


@router.post("/{week_start}/copy-last-week", response_model=ActionOut)
async def copy_week(week_start: date, body: WeekVersion, access: Writes) -> ActionOut:
    return await _copy_week(access, week_start, body.version)


@router.post("/{week_start}/copy-employee-week", response_model=ActionOut)
async def copy_employee(week_start: date, body: EmployeeWeekAction, access: Writes) -> ActionOut:
    return await _copy_week(access, week_start, body.version, body.employee_id)


@router.post("/{week_start}/copy-day", response_model=ActionOut)
async def copy_day(week_start: date, body: CopyDay, access: Writes) -> ActionOut:
    if (
        len(set(body.targets)) != len(body.targets)
        or body.source in body.targets
        or any(monday(d) != week_start for d in [body.source, *body.targets])
    ):
        raise AppError(
            "VALIDATION_ERROR", "Choose different target days in the same week.", status_code=422
        )
    week = await lock_week(access, week_start, body.version)
    selected = await rows(access, week_start, await write_ids(access))
    source = [(r, day) for r, _, _ in selected if r.date == body.source for day in body.targets]
    if len(source) > 5000:
        raise AppError("ROTA_TOO_LARGE", "Copy fewer shifts at a time.", status_code=422)
    target = [r for r, _, _ in selected if r.date in body.targets]
    return await _replace(access, week, source, target)
