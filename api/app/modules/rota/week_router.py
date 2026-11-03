"""Scoped week grid and serialized optimistic shift edits (T9.5)."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.core.errors import NotFoundError
from app.core.rbac_matrix import Scope
from app.modules.attendance.router import _company
from app.modules.employees.models import Employee
from app.modules.rbac.deps import Access, require
from app.modules.rota.models import ShiftType
from app.modules.rota.warnings import warnings
from app.modules.rota.week_models import RotaWeek, ScheduledShift
from app.modules.rota.week_schemas import ActionOut, RotaPerson, ShiftIn, ShiftSaved, WeekOut
from app.modules.rota.weeks import (
    check_monday,
    lock_week,
    monday,
    rows,
    save,
    shift_out,
    touch,
    write_ids,
)

router = APIRouter(prefix="/rota", tags=["rota"])
Reads = Annotated[Access, Depends(require("rota.duty_roster.read"))]
Writes = Annotated[Access, Depends(require("rota.duty_roster.write"))]


@router.get("/weeks/{week_start}", response_model=WeekOut)
async def week(
    week_start: date,
    access: Reads,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    search: Annotated[str, Query(max_length=100)] = "",
) -> WeekOut:
    check_monday(week_start)
    last = week_start + timedelta(days=6)
    query = select(Employee).where(
        Employee.status != "archived",
        Employee.hire_date <= last,
        Employee.leave_date.is_(None) | (Employee.leave_date >= week_start),
    )
    if access.scope is Scope.REPORTS:
        ids = (
            await access.reports.reports_of(access.employee_id)
            if access.employee_id
            else frozenset()
        )
        query = query.where(Employee.id.in_(ids))
    if search.strip():
        # Escape SQL LIKE wildcards so a name search has literal semantics.
        term = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(
            (Employee.first_name + " " + Employee.last_name).ilike(f"%{term}%")
            | Employee.employee_number.ilike(f"%{term}%")
        )
    people = list(
        (
            await access.db.execute(
                query.order_by(Employee.last_name, Employee.first_name, Employee.id)
                .offset(offset)
                .limit(limit + 1)
            )
        ).scalars()
    )
    selected = people[:limit]
    writable = await write_ids(access)
    company = await _company(access)
    selected_rows = await rows(access, week_start, [p.id for p in selected])
    shifts = [shift_out(r, e, name, ZoneInfo(company.timezone)) for r, e, name in selected_rows]
    stored = (
        await access.db.execute(select(RotaWeek).where(RotaWeek.week_start == week_start))
    ).scalar_one_or_none()
    totals = {
        (week_start + timedelta(days=i)).isoformat(): sum(
            (s.hours for s in shifts if s.date == week_start + timedelta(days=i)), Decimal(0)
        )
        for i in range(7)
    }
    return WeekOut(
        week_start=week_start,
        status=stored.status if stored else "draft",
        version=stored.version if stored else 0,
        published_at=stored.published_at if stored else None,
        timezone=company.timezone,
        people=[
            RotaPerson(
                id=p.id,
                name=f"{p.first_name} {p.last_name}",
                employee_number=p.employee_number,
                opted_out_48h_week=p.opted_out_48h_week,
                can_write=writable is None or p.id in writable,
            )
            for p in selected
        ],
        shifts=shifts,
        warnings=await warnings(access, week_start, selected),
        totals=totals,
        not_scheduled=[p.id for p in selected if not any(s.employee_id == p.id for s in shifts)],
        next_offset=offset + limit if len(people) > limit else None,
    )


async def _saved(access: Access, row: ScheduledShift, version: int) -> ShiftSaved:
    company = await _company(access)
    employee = (
        await access.db.execute(select(Employee).where(Employee.id == row.employee_id))
    ).scalar_one()
    name = (
        (
            await access.db.execute(select(ShiftType.name).where(ShiftType.id == row.shift_type_id))
        ).scalar_one_or_none()
        if row.shift_type_id
        else None
    )
    return ShiftSaved(
        shift=shift_out(row, employee, name, ZoneInfo(company.timezone)), version=version
    )


@router.post("/scheduled-shifts", status_code=201, response_model=ShiftSaved)
async def create_scheduled_shift(body: ShiftIn, access: Writes) -> ShiftSaved:
    week = await lock_week(access, monday(body.date), body.version)
    row = await save(access, week, body)
    touch(week)
    result = await _saved(access, row, week.version)
    await access.db.commit()
    return result


@router.put("/scheduled-shifts/{shift_id}", response_model=ShiftSaved)
async def update_scheduled_shift(shift_id: uuid.UUID, body: ShiftIn, access: Writes) -> ShiftSaved:
    # Hide foreign and out-of-report identifiers before checking the week version.
    existing = (
        await access.db.execute(select(ScheduledShift).where(ScheduledShift.id == shift_id))
    ).scalar_one_or_none()
    if existing is None or not await access.can_reach(existing.employee_id):
        raise NotFoundError
    week = await lock_week(access, monday(existing.date), body.version)
    row = (
        await access.db.execute(
            select(ScheduledShift)
            .where(ScheduledShift.id == shift_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    row = await save(access, week, body, row)
    touch(week)
    result = await _saved(access, row, week.version)
    await access.db.commit()
    return result


@router.delete("/scheduled-shifts/{shift_id}", response_model=ActionOut)
async def delete_shift(
    shift_id: uuid.UUID, access: Writes, version: Annotated[int, Query(ge=0)]
) -> ActionOut:
    row = (
        await access.db.execute(select(ScheduledShift).where(ScheduledShift.id == shift_id))
    ).scalar_one_or_none()
    if row is None or not await access.can_reach(row.employee_id):
        raise NotFoundError
    week = await lock_week(access, monday(row.date), version)
    await access.db.delete(row)
    touch(week)
    await access.audit(
        "rota.shift_removed",
        entity_type="employee",
        entity_id=row.employee_id,
        after={"shift_id": str(row.id), "date": row.date.isoformat()},
    )
    await access.db.commit()
    return ActionOut(count=1, version=week.version)
