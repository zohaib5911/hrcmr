"""Shared week locking, scoped schedule writes and company-local projections."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.rbac_matrix import Scope, scope_for
from app.modules.attendance.router import _company
from app.modules.attendance.service import _wall
from app.modules.companies.models import Company
from app.modules.employees.models import Employee
from app.modules.rota.models import ShiftType
from app.modules.rota.week_models import RotaWeek, ScheduledShift
from app.modules.rota.week_schemas import ShiftIn, ShiftOut

if TYPE_CHECKING:
    from app.modules.rbac.deps import Access


ACTION_LIMIT = 5000  # shifts one action may load


def monday(day: date) -> date:
    try:
        start = day - timedelta(days=day.weekday())
        start + timedelta(days=6)
    except OverflowError as error:
        raise AppError("VALIDATION_ERROR", "Choose a valid week.", status_code=422) from error
    return start


def check_monday(day: date) -> None:
    if monday(day) != day:
        raise AppError(
            "VALIDATION_ERROR", "Choose the Monday that starts this week.", status_code=422
        )


async def write_ids(access: Access) -> frozenset[uuid.UUID] | None:
    permission = scope_for(access.role, "rota.duty_roster.write")
    if permission is Scope.ALL:
        return None
    if permission is Scope.REPORTS and access.employee_id:
        return await access.reports.reports_of(access.employee_id)
    return frozenset()


async def lock_week(access: Access, start: date, version: int) -> RotaWeek:
    check_monday(start)
    if access.scope is Scope.REPORTS and not await write_ids(access):
        raise ForbiddenError("Your account needs linked reports to change their rota.")
    await access.db.execute(
        select(Company.id).where(Company.id == access.company_id).with_for_update()
    )
    week = (
        await access.db.execute(
            select(RotaWeek).where(RotaWeek.week_start == start).with_for_update()
        )
    ).scalar_one_or_none()
    if week is None:
        if version != 0:
            raise ConflictError("The rota changed. Reload the week and try again.")
        week = RotaWeek(
            company_id=access.company_id,
            week_start=start,
            status="draft",
            version=0,
            published_shifts=[],
        )
        access.db.add(week)
        await access.db.flush()
    if week.version != version:
        raise ConflictError("The rota changed. Reload the week and review your action again.")
    return week


def touch(week: RotaWeek) -> None:
    week.version += 1
    week.status = "draft"


def paid(row: ScheduledShift) -> Decimal:
    return (
        Decimal(str((row.ends_at - row.starts_at).total_seconds())) / 3600
        - Decimal(row.unpaid_break_minutes) / 60
    ).quantize(Decimal("0.01"))


def shift_out(
    row: ScheduledShift, employee: Employee, shift_name: str | None, zone: ZoneInfo
) -> ShiftOut:
    start, end = row.starts_at.astimezone(zone), row.ends_at.astimezone(zone)
    return ShiftOut(
        id=row.id,
        employee_id=row.employee_id,
        employee_name=f"{employee.first_name} {employee.last_name}",
        date=row.date,
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        starts_local=start.strftime("%H:%M"),
        ends_local=end.strftime("%H:%M"),
        starts_fold=start.fold,
        ends_fold=end.fold,
        unpaid_break_minutes=row.unpaid_break_minutes,
        hours=paid(row),
        shift_type_id=row.shift_type_id,
        shift_name=shift_name,
        note=row.note,
    )


async def rows(
    access: Access, start: date, ids: list[uuid.UUID] | frozenset[uuid.UUID] | None = None
) -> list[tuple[ScheduledShift, Employee, str | None]]:
    query = (
        select(ScheduledShift, Employee, ShiftType.name)
        .join(Employee, Employee.id == ScheduledShift.employee_id)
        .outerjoin(ShiftType, ShiftType.id == ScheduledShift.shift_type_id)
        .where(ScheduledShift.date >= start, ScheduledShift.date <= start + timedelta(days=6))
    )
    if ids is not None:
        query = query.where(ScheduledShift.employee_id.in_(ids))
    result = (
        await access.db.execute(
            query.order_by(ScheduledShift.date, ScheduledShift.starts_at, ScheduledShift.id).limit(
                ACTION_LIMIT + 1
            )
        )
    ).all()
    if len(result) > ACTION_LIMIT:
        raise AppError(
            "ROTA_TOO_LARGE", "This week has too many shifts for one action.", status_code=422
        )
    return [(r, e, name) for r, e, name in result]


async def save(
    access: Access, week: RotaWeek, body: ShiftIn, row: ScheduledShift | None = None
) -> ScheduledShift:
    if monday(body.date) != week.week_start:
        raise AppError(
            "VALIDATION_ERROR",
            "Choose a date in the selected rota week.",
            status_code=422,
            field="date",
        )
    if not await access.can_reach(body.employee_id) or (
        row and not await access.can_reach(row.employee_id)
    ):
        raise NotFoundError
    ids = {body.employee_id, row.employee_id} if row else {body.employee_id}
    people = list(
        (
            await access.db.execute(
                select(Employee).where(Employee.id.in_(ids)).order_by(Employee.id).with_for_update()
            )
        ).scalars()
    )
    employee = next((p for p in people if p.id == body.employee_id), None)
    if employee is None:
        raise NotFoundError
    if (
        employee.status == "archived"
        or body.date < employee.hire_date
        or (employee.leave_date and body.date > employee.leave_date)
    ):
        raise AppError(
            "VALIDATION_ERROR",
            "Choose a date within this employee's employment.",
            status_code=422,
            field="date",
        )
    if body.shift_type_id is not None:
        template = (
            await access.db.execute(
                select(ShiftType.id).where(
                    ShiftType.id == body.shift_type_id, ShiftType.archived_at.is_(None)
                )
            )
        ).first()
        if template is None:
            raise NotFoundError
    zone = ZoneInfo((await _company(access)).timezone)
    try:
        start = _wall(body.date, body.starts_at, zone, body.starts_fold, "starts_at")
        end = _wall(
            body.date + timedelta(days=body.ends_at <= body.starts_at),
            body.ends_at,
            zone,
            body.ends_fold,
            "ends_at",
        )
    except OverflowError as error:
        raise AppError("VALIDATION_ERROR", "Choose a valid shift date.", status_code=422) from error
    if end <= start or body.unpaid_break_minutes * 60 > (end - start).total_seconds():
        raise AppError(
            "VALIDATION_ERROR",
            "The break cannot exceed the shift duration.",
            status_code=422,
            field="unpaid_break_minutes",
        )
    overlap = select(ScheduledShift.id).where(
        ScheduledShift.employee_id == employee.id,
        ScheduledShift.starts_at < end,
        ScheduledShift.ends_at > start,
    )
    if row:
        overlap = overlap.where(ScheduledShift.id != row.id)
    if (await access.db.execute(overlap)).first() is not None:
        raise ConflictError("This employee already has a shift at that time.")
    old_employee = row.employee_id if row else None
    if row is None:
        row = ScheduledShift(company_id=access.company_id, rota_week_id=week.id)
        access.db.add(row)
    row.employee_id, row.date = employee.id, body.date
    row.starts_at, row.ends_at = start, end
    row.unpaid_break_minutes, row.shift_type_id = body.unpaid_break_minutes, body.shift_type_id
    row.note = body.note.strip() or None if body.note else None
    await access.db.flush()
    await access.audit(
        "rota.shift_saved",
        entity_type="employee",
        entity_id=employee.id,
        after={
            "shift_id": str(row.id),
            "date": row.date.isoformat(),
            "starts_at": start.isoformat(),
            "ends_at": end.isoformat(),
            "break_minutes": row.unpaid_break_minutes,
            "reassigned": old_employee is not None and old_employee != employee.id,
        },
    )
    return row
