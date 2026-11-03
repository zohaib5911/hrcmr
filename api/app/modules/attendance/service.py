"""Shared attendance validation and transactional row writes for manual/import/grid entry."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.rbac_matrix import Scope
from app.modules.attendance.models import AttendanceRecord
from app.modules.companies.models import Company
from app.modules.employees.models import Employee

if TYPE_CHECKING:
    from app.modules.attendance.schemas import AttendanceIn
    from app.modules.rbac.deps import Access
WORKED = frozenset({"present", "late", "half_day"})


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


def times(
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


def snapshot(row: AttendanceRecord) -> dict[str, Any]:
    return {
        "status": row.status,
        "clock_in": row.clock_in.isoformat() if row.clock_in else None,
        "clock_out": row.clock_out.isoformat() if row.clock_out else None,
        "unpaid_break_minutes": row.unpaid_break_minutes,
        "hours": str(row.hours) if row.hours is not None else None,
        "source": row.source,
    }


async def save_record(
    access: Access, body: AttendanceIn, *, source: Literal["manual", "import", "grid"] = "manual"
) -> tuple[AttendanceRecord, Employee, Company]:
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
    company = (
        await access.db.execute(select(Company).where(Company.id == access.company_id))
    ).scalar_one()
    if (
        source == "grid"
        and body.status in WORKED
        and body.clock_in is None
        and body.clock_out is None
        and body.unpaid_break_minutes == 0
    ):
        start, end, hours = None, None, None
    else:
        start, end, hours = times(body, ZoneInfo(company.timezone))
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
    before = snapshot(row) if row else None
    old_note = row.note if row else None
    if row is None:
        row = AttendanceRecord(
            company_id=access.company_id, employee_id=employee.id, date=body.date
        )
        access.db.add(row)
    row.status = body.status
    row.clock_in, row.clock_out, row.hours = start, end, hours
    row.unpaid_break_minutes, row.note = body.unpaid_break_minutes, body.note
    row.source = source
    row.geo = None
    await access.db.flush()
    after = snapshot(row)
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
    return row, employee, company
