"""Serialized own clocking and reporting-chain weekly timesheet approval (T9.3)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from app.modules.attendance.clock_schemas import (
    ClockIn,
    ClockOut,
    ClockState,
    TimesheetApprove,
    TimesheetOut,
    TimesheetPage,
)
from app.modules.attendance.models import AttendanceRecord, TimesheetApproval
from app.modules.attendance.router import Reads, Writes, _company, _out
from app.modules.attendance.schemas import AttendanceOut
from app.modules.attendance.service import WORKED, snapshot
from app.modules.employees.models import Employee
from app.modules.rbac.deps import Access, require
from app.modules.rota.late import clock_status

if TYPE_CHECKING:
    from app.modules.companies.models import Company

router = APIRouter(prefix="/attendance", tags=["attendance"])
Approvers = Annotated[Access, Depends(require("attendance.timesheet.approve"))]


def now() -> datetime:
    return datetime.now(UTC)


async def _person(access: Access, *, lock: bool = False) -> Employee:
    if access.employee_id is None:
        raise ForbiddenError("Your account needs a linked employee record to clock in or out.")
    query = select(Employee).where(Employee.id == access.employee_id)
    if lock:
        query = query.with_for_update()
    employee = (await access.db.execute(query)).scalar_one_or_none()
    if employee is None:
        raise NotFoundError
    return employee


async def _active(access: Access, employee: Employee) -> AttendanceRecord | None:
    return (
        await access.db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.employee_id == employee.id,
                AttendanceRecord.source == "clock",
                AttendanceRecord.clock_in.is_not(None),
                AttendanceRecord.clock_out.is_(None),
            )
        )
    ).scalar_one_or_none()


def _location(body: ClockIn, company: Company, instant: datetime) -> dict[str, object] | None:
    if body.location is None:
        return None
    if not company.clock_geolocation_enabled or not body.location_consent:
        raise ForbiddenError("Location needs company enablement and your consent for this action.")
    return {**body.location.model_dump(), "consented_at": instant.isoformat()}


@router.get("/clock", response_model=ClockState)
async def clock_state(access: Reads) -> ClockState:
    company = await _company(access)
    employee = await _person(access) if access.employee_id else None
    active = await _active(access, employee) if employee else None
    return ClockState(
        employee_name=f"{employee.first_name} {employee.last_name}" if employee else None,
        timezone=company.timezone,
        location_enabled=company.clock_geolocation_enabled,
        active=_out(active, employee, ZoneInfo(company.timezone)) if active and employee else None,
    )


@router.post("/clock-in", response_model=ClockState)
async def clock_in(body: ClockIn, access: Writes) -> ClockState:
    employee = await _person(access, lock=True)
    company = await _company(access)
    instant = now()
    location = _location(body, company, instant)
    day = instant.astimezone(ZoneInfo(company.timezone)).date()
    if (
        employee.status == "archived"
        or day < employee.hire_date
        or (employee.leave_date is not None and day > employee.leave_date)
    ):
        raise ConflictError("You can only clock in during your employment.")
    active = await _active(access, employee)
    if active is None:
        existing = (
            await access.db.execute(
                select(AttendanceRecord.id).where(
                    AttendanceRecord.employee_id == employee.id, AttendanceRecord.date == day
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError("Attendance is already recorded today. Ask HR to review it.")
        active = AttendanceRecord(
            company_id=access.company_id,
            employee_id=employee.id,
            date=day,
            status=await clock_status(access, company, employee, instant),
            source="clock",
            clock_in=instant,
            unpaid_break_minutes=0,
            note=body.note.strip() or None if body.note else None,
            geo={"in": location} if location else None,
        )
        access.db.add(active)
        await access.db.flush()
        await access.audit(
            "attendance.clocked_in",
            entity_type="employee",
            entity_id=employee.id,
            after={
                "attendance_id": str(active.id),
                "date": day.isoformat(),
                "location_shared": location is not None,
            },
        )
    await access.db.commit()
    return ClockState(
        employee_name=f"{employee.first_name} {employee.last_name}",
        timezone=company.timezone,
        location_enabled=company.clock_geolocation_enabled,
        active=_out(active, employee, ZoneInfo(company.timezone)),
    )


@router.post("/clock-out", response_model=AttendanceOut)
async def clock_out(body: ClockOut, access: Writes) -> AttendanceOut:
    employee = await _person(access, lock=True)
    company = await _company(access)
    row = (
        await access.db.execute(
            select(AttendanceRecord)
            .where(
                AttendanceRecord.id == body.record_id,
                AttendanceRecord.employee_id == employee.id,
                AttendanceRecord.source == "clock",
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None or row.clock_in is None:
        raise NotFoundError
    if row.clock_out is not None:
        return _out(row, employee, ZoneInfo(company.timezone))
    instant = now()
    location = _location(body, company, instant)
    seconds = (
        Decimal(str((instant - row.clock_in).total_seconds())) - body.unpaid_break_minutes * 60
    )
    if seconds < 0 or seconds > 9999 * 3600:
        raise AppError(
            "VALIDATION_ERROR",
            "The break cannot exceed the recorded shift. Ask HR to review an incorrect clock-in.",
            status_code=422,
            field="unpaid_break_minutes",
        )
    row.clock_out = instant
    row.unpaid_break_minutes = body.unpaid_break_minutes
    row.hours = (seconds / 3600).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if body.note is not None:
        row.note = body.note.strip() or None
    if location:
        row.geo = {**(row.geo or {}), "out": location}
    await access.db.flush()
    await access.audit(
        "attendance.clocked_out",
        entity_type="employee",
        entity_id=employee.id,
        after={
            **snapshot(row),
            "attendance_id": str(row.id),
            "date": row.date.isoformat(),
            "location_shared": location is not None,
        },
    )
    await access.db.commit()
    return _out(row, employee, ZoneInfo(company.timezone))


def _week(start: date) -> date:
    try:
        monday = start - timedelta(days=start.weekday())
        monday + timedelta(days=6)
    except OverflowError as error:
        raise AppError("VALIDATION_ERROR", "Choose a valid week.", status_code=422) from error
    return monday


def _sheet_id(company_id: uuid.UUID, employee_id: uuid.UUID, start: date) -> uuid.UUID:
    # A stable projection identifier; GET never creates approval rows.
    return uuid.uuid5(uuid.NAMESPACE_URL, f"timesheet:{company_id}:{employee_id}:{start}")


async def _sheet(access: Access, employee: Employee, start: date) -> TimesheetOut:
    end = start + timedelta(days=6)
    records = list(
        (
            await access.db.execute(
                select(AttendanceRecord)
                .where(
                    AttendanceRecord.employee_id == employee.id,
                    AttendanceRecord.date >= start,
                    AttendanceRecord.date <= end,
                )
                .order_by(AttendanceRecord.date, AttendanceRecord.id)
            )
        ).scalars()
    )
    fingerprint = hashlib.sha256(
        json.dumps(
            [
                {
                    **snapshot(r),
                    "id": str(r.id),
                    "date": r.date.isoformat(),
                    "updated_at": r.updated_at.isoformat(),
                    "note": r.note,
                }
                for r in records
            ],
            sort_keys=True,
        ).encode()
    ).hexdigest()
    approval = (
        await access.db.execute(
            select(TimesheetApproval).where(
                TimesheetApproval.employee_id == employee.id,
                TimesheetApproval.period_start == start,
            )
        )
    ).scalar_one_or_none()
    current = approval is not None and approval.fingerprint == fingerprint
    company = await _company(access)
    return TimesheetOut(
        id=_sheet_id(access.company_id, employee.id, start),
        employee_id=employee.id,
        employee_name=f"{employee.first_name} {employee.last_name}",
        period_start=start,
        period_end=end,
        hours=sum((r.hours or Decimal(0) for r in records), Decimal(0)),
        records=[_out(r, employee, ZoneInfo(company.timezone)) for r in records],
        incomplete=not records
        or any(
            r.status in WORKED and (r.clock_in is None or r.clock_out is None or r.hours is None)
            for r in records
        ),
        fingerprint=fingerprint,
        approved_at=approval.approved_at if current and approval else None,
        approved_by=approval.approved_by if current and approval else None,
    )


async def _report_ids(access: Access) -> frozenset[uuid.UUID]:
    return (
        await access.reports.reports_of(access.employee_id) if access.employee_id else frozenset()
    )


@router.get("/timesheets", response_model=TimesheetPage)
async def timesheets(
    access: Approvers,
    start: date,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> TimesheetPage:
    monday = _week(start)
    ids = await _report_ids(access)
    people = list(
        (
            await access.db.execute(
                select(Employee)
                .where(Employee.id.in_(ids))
                .order_by(Employee.last_name, Employee.first_name, Employee.id)
                .offset(offset)
                .limit(limit + 1)
            )
        ).scalars()
    )
    return TimesheetPage(
        items=[await _sheet(access, e, monday) for e in people[:limit]],
        next_offset=offset + limit if len(people) > limit else None,
    )


@router.post("/timesheets/{timesheet_id}/approve", response_model=TimesheetOut)
async def approve(
    timesheet_id: uuid.UUID, body: TimesheetApprove, access: Approvers
) -> TimesheetOut:
    start = _week(body.period_start)
    if body.employee_id == access.employee_id:
        raise ForbiddenError("You cannot approve your own timesheet.")
    if body.employee_id not in await _report_ids(access):
        raise NotFoundError
    if timesheet_id != _sheet_id(access.company_id, body.employee_id, start):
        raise NotFoundError
    employee = (
        await access.db.execute(
            select(Employee).where(Employee.id == body.employee_id).with_for_update()
        )
    ).scalar_one_or_none()
    if employee is None:
        raise NotFoundError
    sheet = await _sheet(access, employee, start)
    if sheet.fingerprint != body.fingerprint:
        raise ConflictError("Attendance changed. Reload and review this timesheet again.")
    company = await _company(access)
    if sheet.period_end >= now().astimezone(ZoneInfo(company.timezone)).date():
        raise ConflictError("Approve a timesheet after the week has ended.")
    if sheet.incomplete:
        raise ConflictError("Complete the missing clock times before approval.")
    if sheet.approved_at is not None:
        return sheet
    approval = (
        await access.db.execute(
            select(TimesheetApproval).where(
                TimesheetApproval.employee_id == employee.id,
                TimesheetApproval.period_start == start,
            )
        )
    ).scalar_one_or_none()
    if approval is None:
        approval = TimesheetApproval(
            company_id=access.company_id,
            employee_id=employee.id,
            period_start=start,
            period_end=sheet.period_end,
        )
        access.db.add(approval)
    approval.fingerprint = sheet.fingerprint
    approval.approved_by = access.caller.user_id
    approval.approved_at = now()
    await access.db.flush()
    await access.audit(
        "attendance.timesheet_approved",
        entity_type="employee",
        entity_id=employee.id,
        after={
            "timesheet_id": str(timesheet_id),
            "period_start": start.isoformat(),
            "period_end": sheet.period_end.isoformat(),
            "hours": str(sheet.hours),
        },
    )
    result = sheet.model_copy(
        update={"approved_at": approval.approved_at, "approved_by": approval.approved_by}
    )
    await access.db.commit()
    return result
