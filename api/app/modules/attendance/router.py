"""Scoped attendance reads and serialized, audited manual entry (T9.1)."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any, cast
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.rbac_matrix import Scope
from app.modules.attendance.models import AttendanceRecord
from app.modules.attendance.schemas import (
    AttendanceIn,
    AttendanceOut,
    AttendancePage,
    AttendanceStatus,
    AttendanceSummary,
)
from app.modules.companies.models import Company
from app.modules.employees.models import Employee
from app.modules.rbac.deps import Access, require

router = APIRouter(tags=["attendance"])
Reads = Annotated[Access, Depends(require("attendance.record.read"))]
Writes = Annotated[Access, Depends(require("attendance.record.write"))]
STATUSES = ("present", "absent", "late", "half_day", "on_leave", "sick")
WORKED = frozenset({"present", "late", "half_day"})


async def _company(access: Access) -> Company:
    return (
        await access.db.execute(select(Company).where(Company.id == access.company_id))
    ).scalar_one()


async def _ids(
    access: Access, employee_id: uuid.UUID | None, *, own: bool
) -> list[uuid.UUID] | None:
    if employee_id is not None and not await access.can_reach(employee_id):
        raise NotFoundError
    if own or access.scope is Scope.OWN:
        if employee_id is not None and employee_id != access.employee_id:
            raise NotFoundError
        return [access.employee_id] if access.employee_id else []
    if access.scope is Scope.REPORTS:
        reports = (
            await access.reports.reports_of(access.employee_id) if access.employee_id else set()
        )
        return (
            [employee_id] if employee_id is not None and employee_id in reports else list(reports)
        )
    return [employee_id] if employee_id is not None else None


def _out(row: AttendanceRecord, employee: Employee, zone: ZoneInfo) -> AttendanceOut:
    start = row.clock_in.astimezone(zone) if row.clock_in else None
    end = row.clock_out.astimezone(zone) if row.clock_out else None
    return AttendanceOut(
        id=row.id,
        employee_id=row.employee_id,
        employee_name=f"{employee.first_name} {employee.last_name}",
        date=row.date,
        status=cast("AttendanceStatus", row.status),
        clock_in=row.clock_in,
        clock_out=row.clock_out,
        clock_in_local=start.strftime("%H:%M") if start else None,
        clock_out_local=end.strftime("%H:%M") if end else None,
        clock_in_fold=start.fold if start else None,
        clock_out_fold=end.fold if end else None,
        unpaid_break_minutes=row.unpaid_break_minutes,
        hours=row.hours,
        note=row.note,
        source=row.source,
        leave_request_id=row.leave_request_id,
    )


async def _list(
    access: Access,
    start: date,
    end: date,
    employee_id: uuid.UUID | None,
    status: AttendanceStatus | None,
    offset: int,
    limit: int,
    *,
    own: bool,
) -> AttendancePage:
    if end < start or (end - start).days > 366:
        raise AppError(
            "VALIDATION_ERROR",
            "Choose a date range of up to one year.",
            status_code=422,
            field="end",
        )
    ids = await _ids(access, employee_id, own=own)
    query = (
        select(AttendanceRecord, Employee)
        .join(Employee, Employee.id == AttendanceRecord.employee_id)
        .where(AttendanceRecord.date >= start, AttendanceRecord.date <= end)
    )
    if ids is not None:
        query = query.where(AttendanceRecord.employee_id.in_(ids))
    if status is not None:
        query = query.where(AttendanceRecord.status == status)
    total = (
        await access.db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar_one()
    rows = (
        await access.db.execute(
            query.order_by(AttendanceRecord.date.desc(), Employee.last_name, Employee.id)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    company = await _company(access)
    return AttendancePage(
        items=[_out(r, e, ZoneInfo(company.timezone)) for r, e in rows],
        total=total,
        next_offset=offset + limit if offset + len(rows) < total else None,
        timezone=company.timezone,
    )


@router.get("/attendance-records", response_model=AttendancePage)
async def records(
    access: Reads,
    start: date,
    end: date,
    employee_id: uuid.UUID | None = None,
    status: AttendanceStatus | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AttendancePage:
    return await _list(access, start, end, employee_id, status, offset, limit, own=False)


@router.get("/attendance-records/own", response_model=AttendancePage)
async def own_records(
    access: Reads,
    start: date,
    end: date,
    status: AttendanceStatus | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AttendancePage:
    return await _list(access, start, end, None, status, offset, limit, own=True)


@router.get("/attendance-records/summary", response_model=AttendanceSummary)
async def summary(
    access: Reads, on: date, employee_id: uuid.UUID | None = None
) -> AttendanceSummary:
    ids = await _ids(access, employee_id, own=False)
    people = select(Employee.id).where(
        Employee.hire_date <= on,
        Employee.leave_date.is_(None) | (Employee.leave_date >= on),
        Employee.status != "archived",
    )
    if ids is not None:
        people = people.where(Employee.id.in_(ids))
    eligible = list((await access.db.execute(people)).scalars())
    counts = dict(
        (
            await access.db.execute(
                select(AttendanceRecord.status, func.count())
                .where(AttendanceRecord.date == on, AttendanceRecord.employee_id.in_(eligible))
                .group_by(AttendanceRecord.status)
            )
        ).all()
    )
    company = await _company(access)
    return AttendanceSummary(
        on=on,
        timezone=company.timezone,
        employees=len(eligible),
        counts={s: int(counts.get(s, 0)) for s in STATUSES},
        not_recorded=len(eligible) - sum(counts.values()),
    )


def _wall(day: date, clock: time, zone: ZoneInfo, fold: int | None, field: str) -> datetime:
    local = datetime.combine(day, clock, tzinfo=zone)
    possibilities = [local.replace(fold=f) for f in (0, 1)]
    valid = [
        t
        for t in possibilities
        if t.astimezone(UTC).astimezone(zone).replace(tzinfo=None) == local.replace(tzinfo=None)
    ]
    if not valid:
        raise AppError(
            "INVALID_LOCAL_TIME",
            "This time does not occur because the clocks move forward. Choose a valid time.",
            status_code=422,
            field=field,
        )
    if len({t.utcoffset() for t in valid}) > 1 and fold is None:
        raise AppError(
            "AMBIGUOUS_LOCAL_TIME",
            "This time occurs twice when the clocks go back. "
            "Choose the first or second occurrence.",
            status_code=422,
            field=field,
        )
    return local.replace(fold=fold or 0).astimezone(UTC)


def _times(
    body: AttendanceIn, zone: ZoneInfo
) -> tuple[datetime | None, datetime | None, Decimal | None]:
    if body.status not in WORKED:
        if body.clock_in is not None or body.clock_out is not None or body.unpaid_break_minutes:
            raise AppError(
                "VALIDATION_ERROR",
                "Absence records do not have clock times or breaks.",
                status_code=422,
                field="clock_in",
            )
        return None, None, None
    if body.clock_in is None or body.clock_out is None:
        raise AppError(
            "VALIDATION_ERROR",
            "Enter clock-in and clock-out times for worked attendance.",
            status_code=422,
            field="clock_in",
        )
    start = _wall(body.date, body.clock_in, zone, body.clock_in_fold, "clock_in")
    end_day = body.date + timedelta(days=body.clock_out <= body.clock_in)
    end = _wall(end_day, body.clock_out, zone, body.clock_out_fold, "clock_out")
    seconds = int((end - start).total_seconds()) - body.unpaid_break_minutes * 60
    if seconds < 0:
        raise AppError(
            "VALIDATION_ERROR",
            "The unpaid break cannot exceed the recorded shift.",
            status_code=422,
            field="unpaid_break_minutes",
        )
    return start, end, (Decimal(seconds) / 3600).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _snapshot(row: AttendanceRecord) -> dict[str, Any]:
    return {
        "status": row.status,
        "clock_in": row.clock_in.isoformat() if row.clock_in else None,
        "clock_out": row.clock_out.isoformat() if row.clock_out else None,
        "unpaid_break_minutes": row.unpaid_break_minutes,
        "hours": str(row.hours) if row.hours is not None else None,
        "source": row.source,
    }


@router.put("/attendance-records", response_model=AttendanceOut)
async def record(body: AttendanceIn, access: Writes) -> AttendanceOut:
    if access.scope is not Scope.ALL:
        raise ForbiddenError("Self-service attendance writes are limited to clocking in and out.")
    employee = (
        await access.db.execute(
            select(Employee).where(Employee.id == body.employee_id).with_for_update()
        )
    ).scalar_one_or_none()
    if employee is None:
        raise NotFoundError
    if (
        employee.status == "archived"
        or body.date < employee.hire_date
        or (employee.leave_date is not None and body.date > employee.leave_date)
    ):
        raise AppError(
            "VALIDATION_ERROR",
            "Choose a date within this employee's employment.",
            status_code=422,
            field="date",
        )
    company = await _company(access)
    start, end, hours = _times(body, ZoneInfo(company.timezone))
    row = (
        await access.db.execute(
            select(AttendanceRecord)
            .where(AttendanceRecord.employee_id == employee.id, AttendanceRecord.date == body.date)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is not None and (row.source == "leave_sync" or row.leave_request_id is not None):
        raise ConflictError(
            "This attendance comes from approved leave and cannot be replaced by a manual record."
        )
    before = _snapshot(row) if row else None
    old_note = row.note if row else None
    if row is None:
        row = AttendanceRecord(
            company_id=access.company_id, employee_id=employee.id, date=body.date
        )
        access.db.add(row)
    row.status = body.status
    row.clock_in, row.clock_out, row.hours = start, end, hours
    row.unpaid_break_minutes, row.note = body.unpaid_break_minutes, body.note
    row.source = "manual"
    row.geo = None
    await access.db.flush()
    after = _snapshot(row)
    if before != after or old_note != body.note:
        await access.audit(
            "attendance.recorded" if before is None else "attendance.updated",
            entity_type="employee",
            entity_id=employee.id,
            before=before,
            after={
                **after,
                "attendance_id": str(row.id),
                "date": body.date.isoformat(),
                "note_changed": old_note != body.note,
            },
        )
    await access.db.commit()
    return _out(row, employee, ZoneInfo(company.timezone))
