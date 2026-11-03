"""Advisory leave/holiday, weekly hours and rest checks for scoped rota projections."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import timedelta
from decimal import Decimal
from itertools import pairwise
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.modules.attendance.router import _company
from app.modules.employees.models import EmployeeAssignment
from app.modules.holidays.models import BankHoliday, CompanyHoliday
from app.modules.leave.request_models import LeaveRequest
from app.modules.rota.models import DayOffPattern
from app.modules.rota.week_models import ScheduledShift
from app.modules.rota.week_schemas import RotaWarning
from app.modules.rota.weeks import paid

if TYPE_CHECKING:
    from datetime import date

    from app.modules.employees.models import Employee
    from app.modules.rbac.deps import Access


async def warnings(access: Access, start: date, people: list[Employee]) -> list[RotaWarning]:
    ids = [p.id for p in people]
    end = start + timedelta(days=6)
    company = await _company(access)
    zone = ZoneInfo(company.timezone)
    shifts = list(
        (
            await access.db.execute(
                select(ScheduledShift)
                .where(
                    ScheduledShift.employee_id.in_(ids),
                    ScheduledShift.date >= start - timedelta(days=int(start.toordinal() > 1)),
                    ScheduledShift.date <= end + timedelta(days=1),
                )
                .order_by(ScheduledShift.employee_id, ScheduledShift.starts_at)
            )
        ).scalars()
    )
    requests = list(
        (
            await access.db.execute(
                select(LeaveRequest).where(
                    LeaveRequest.employee_id.in_(ids),
                    LeaveRequest.status == "approved",
                    LeaveRequest.start_date <= end + timedelta(days=1),
                    LeaveRequest.end_date >= start,
                )
            )
        ).scalars()
    )
    closures = list(
        (
            await access.db.execute(
                select(CompanyHoliday).where(
                    CompanyHoliday.archived_at.is_(None),
                    CompanyHoliday.start_date <= end + timedelta(days=1),
                    CompanyHoliday.end_date >= start,
                )
            )
        ).scalars()
    )
    bank = set(
        (
            await access.db.execute(
                select(BankHoliday.on_date).where(
                    BankHoliday.region == company.bank_holiday_region,
                    BankHoliday.on_date >= start,
                    BankHoliday.on_date <= end + timedelta(days=1),
                )
            )
        ).scalars()
    )
    result: list[RotaWarning] = []
    assignments = list(
        (
            await access.db.execute(
                select(EmployeeAssignment).where(
                    EmployeeAssignment.employee_id.in_(ids),
                    EmployeeAssignment.effective_from <= end + timedelta(days=1),
                    EmployeeAssignment.ended_at.is_(None) | (EmployeeAssignment.ended_at > start),
                )
            )
        ).scalars()
    )
    patterns = list(
        (
            await access.db.execute(
                select(DayOffPattern).where(DayOffPattern.archived_at.is_(None))
            )
        ).scalars()
    )

    def add(employee_id: uuid.UUID, shift_id: uuid.UUID | None, code: str, message: str) -> None:
        result.append(
            RotaWarning(employee_id=employee_id, shift_id=shift_id, code=code, message=message)
        )

    for employee in people:
        mine = [s for s in shifts if s.employee_id == employee.id]
        this_week = [s for s in mine if start <= s.date <= end]
        total = sum((paid(s) for s in this_week), Decimal(0))
        if total > 48 and not employee.opted_out_48h_week:
            add(
                employee.id,
                None,
                "WEEKLY_HOURS",
                f"{total} planned hours exceeds 48 hours; no opt-out is recorded.",
            )
        for shift in this_week:
            assignment = next(
                (
                    a
                    for a in assignments
                    if a.employee_id == employee.id
                    and a.effective_from <= shift.date
                    and (a.ended_at is None or shift.date < a.ended_at)
                ),
                None,
            )
            pattern = next(
                (
                    p
                    for p in patterns
                    if assignment
                    and p.department_id == assignment.department_id
                    and p.designation_id == assignment.designation_id
                    and p.shift_type_id == shift.shift_type_id
                ),
                None,
            )
            first = shift.starts_at.astimezone(zone).date()
            last = (shift.ends_at - timedelta(microseconds=1)).astimezone(zone).date()
            days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
            if any(
                r.employee_id == employee.id
                and any(day.isoformat() in r.working_dates for day in days)
                for r in requests
            ):
                add(employee.id, shift.id, "APPROVED_LEAVE", "This shift overlaps approved leave.")
            if any(any(c.start_date <= day <= c.end_date for day in days) for c in closures):
                add(
                    employee.id,
                    shift.id,
                    "COMPANY_HOLIDAY",
                    "This shift overlaps a company holiday.",
                )
            if pattern and any(d.isoweekday() in pattern.weekdays_off for d in days):
                add(employee.id, shift.id, "DAY_OFF", "This shift overlaps a regular day off.")
            if (
                company.bank_holidays_non_working
                and bank.intersection(days)
                and not (pattern and pattern.works_public_holidays)
            ):
                add(
                    employee.id,
                    shift.id,
                    "BANK_HOLIDAY",
                    "This shift overlaps a non-working public holiday.",
                )
        for previous, following in pairwise(mine):
            rest = (following.starts_at - previous.ends_at).total_seconds() / 3600
            if rest < 11 and (start <= previous.date <= end or start <= following.date <= end):
                add(
                    employee.id,
                    following.id,
                    "REST",
                    f"Only {rest:.2f} hours rest between shifts; review the 11-hour rest warning.",
                )
    return result
