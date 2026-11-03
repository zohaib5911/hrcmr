"""Dated leave plans and conflict checks shared by preview, submission and approval."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction
from math import ceil
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.core.errors import AppError
from app.modules.attendance.models import AttendanceRecord
from app.modules.companies.models import Company
from app.modules.employees.models import Employee, EmployeeAssignment
from app.modules.holidays.models import BankHoliday, CompanyHoliday
from app.modules.leave.calculations import dates, hours_on, standard_day, year_bounds
from app.modules.leave.ledger import ensure_open, working_pattern
from app.modules.leave.request_models import LeaveRequest
from app.modules.leave.request_schemas import LeaveConflict
from app.modules.rota.week_models import ScheduledShift

if TYPE_CHECKING:
    import uuid

    from app.db.session import TenantSession
    from app.modules.leave.request_schemas import LeaveDatesIn


@dataclass(frozen=True)
class RequestPlan:
    quantities: dict[date, Fraction]
    by_year: dict[date, Decimal]

    @property
    def total(self) -> Decimal:
        return sum(self.by_year.values(), Decimal(0)).quantize(Decimal("0.01"))

    def snapshot(self) -> dict[str, str]:
        return {day.isoformat(): str(amount) for day, amount in self.quantities.items()}


async def plan_request(db: TenantSession, employee: Employee, body: LeaveDatesIn) -> RequestPlan:
    start, last = body.start_date, body.end_date
    end = last + timedelta(days=1)
    if start < employee.hire_date or (
        employee.leave_date is not None and last > employee.leave_date
    ):
        raise AppError(
            "VALIDATION_ERROR",
            "Choose dates within this employee's employment.",
            status_code=422,
            field="start_date",
        )
    if employee.status == "archived":
        raise AppError(
            "VALIDATION_ERROR", "Archived employees cannot request leave.", status_code=422
        )
    company = (await db.execute(select(Company).where(Company.id == db.company_id))).scalar_one()
    default, patterns = await working_pattern(db, employee.id, start, end, regular_only=False)
    standard_day(default)
    excluded: set[date] = set()
    if company.bank_holidays_non_working:
        # Read complete regional years, not just holidays inside a short request.
        holidays = (
            (
                await db.execute(
                    select(BankHoliday).where(
                        BankHoliday.region == company.bank_holiday_region,
                        BankHoliday.on_date >= date(start.year, 1, 1),
                        BankHoliday.on_date < date(last.year + 1, 1, 1),
                    )
                )
            )
            .scalars()
            .all()
        )
        if not set(range(start.year, last.year + 1)) <= {h.on_date.year for h in holidays}:
            raise AppError(
                "BANK_HOLIDAYS_UNAVAILABLE",
                "The official regional bank-holiday calendar does not cover these dates yet.",
                status_code=503,
            )
        excluded.update(h.on_date for h in holidays)
    closures = (
        (
            await db.execute(
                select(CompanyHoliday).where(
                    CompanyHoliday.archived_at.is_(None),
                    CompanyHoliday.start_date <= last,
                    CompanyHoliday.end_date >= start,
                )
            )
        )
        .scalars()
        .all()
    )
    excluded.update(
        d
        for c in closures
        for d in dates(max(start, c.start_date), min(end, c.end_date + timedelta(days=1)))
    )
    standard = Fraction(sum(default)) / sum(h > 0 for h in default)
    quantities = {
        d: Fraction(hours_on(d, default, patterns)) / standard
        for d in dates(start, end)
        if d not in excluded and hours_on(d, default, patterns) > 0
    }
    for day, half in ((start, body.half_day_start), (last, body.half_day_end)):
        if half:
            if day not in quantities:
                raise AppError(
                    "VALIDATION_ERROR",
                    "A half-day option must fall on a working day.",
                    status_code=422,
                )
            quantities[day] /= 2
    if not quantities:
        raise AppError(
            "VALIDATION_ERROR",
            "This period contains no working days.",
            status_code=422,
            field="start_date",
        )
    totals: dict[date, Fraction] = {}
    for day, quantity in quantities.items():
        year = year_bounds(day, company.leave_year_start_month_day)[0]
        totals[year] = totals.get(year, Fraction(0)) + quantity
    for year in totals:
        await ensure_open(db, year)
    return RequestPlan(
        quantities, {year: Decimal(ceil(amount * 100)) / 100 for year, amount in totals.items()}
    )


async def conflicts(
    db: TenantSession,
    employee_id: uuid.UUID,
    start: date,
    end: date,
    plan: RequestPlan,
    *,
    exclude: uuid.UUID | None = None,
) -> list[LeaveConflict]:
    requests = (
        (
            await db.execute(
                select(LeaveRequest).where(
                    LeaveRequest.status.in_(("pending", "approved")),
                    LeaveRequest.start_date <= end,
                    LeaveRequest.end_date >= start,
                )
            )
        )
        .scalars()
        .all()
    )
    own = [
        r
        for r in requests
        if r.employee_id == employee_id
        and r.id != exclude
        and set(r.working_dates) & set(plan.snapshot())
    ]
    result = []
    if own:
        result.append(
            LeaveConflict(
                code="EMPLOYEE_OVERLAP",
                message="This employee already has pending or approved leave "
                "on these working days.",
                blocking=True,
            )
        )
    attendance = (
        (
            await db.execute(
                select(AttendanceRecord).where(
                    AttendanceRecord.employee_id == employee_id,
                    AttendanceRecord.date.in_(plan.quantities),
                )
            )
        )
        .scalars()
        .all()
    )
    shifts = (
        await db.execute(
            select(ScheduledShift.id)
            .where(
                ScheduledShift.employee_id == employee_id, ScheduledShift.date.in_(plan.quantities)
            )
            .limit(1)
        )
    ).first()
    if shifts:
        result.append(
            LeaveConflict(
                code="SHIFT_CONFLICT",
                message="Scheduled shifts overlap these dates; review the rota before approval.",
                blocking=False,
            )
        )
    if attendance:
        result.append(
            LeaveConflict(
                code="ATTENDANCE_EXISTS",
                message="Attendance is already recorded on these working days. "
                "Review it before approving leave.",
                blocking=True,
            )
        )
    assignment = (
        await db.execute(
            select(EmployeeAssignment).where(
                EmployeeAssignment.employee_id == employee_id,
                EmployeeAssignment.effective_from <= start,
                EmployeeAssignment.ended_at.is_(None) | (EmployeeAssignment.ended_at > start),
            )
        )
    ).scalar_one_or_none()
    if assignment is not None and assignment.department_id is not None:
        team = set(
            (
                await db.execute(
                    select(EmployeeAssignment.employee_id).where(
                        EmployeeAssignment.department_id == assignment.department_id,
                        EmployeeAssignment.effective_from <= end,
                        EmployeeAssignment.ended_at.is_(None)
                        | (EmployeeAssignment.ended_at > start),
                    )
                )
            ).scalars()
        ) - {employee_id}
        away = {
            r.employee_id
            for r in requests
            if r.employee_id in team
            and r.id != exclude
            and set(r.working_dates) & set(plan.snapshot())
        }
        # Warn when the proposed absence leaves nobody available in the department.
        # This is an advisory minimum of one, not an invented blocking company policy.
        active_team = set(
            (
                await db.execute(
                    select(Employee.id).where(
                        Employee.id.in_(team),
                        Employee.status.in_(("active", "on_leave")),
                        Employee.hire_date <= end,
                        Employee.leave_date.is_(None) | (Employee.leave_date >= start),
                    )
                )
            ).scalars()
        )
        for day in plan.snapshot():
            away_on_day = {
                r.employee_id
                for r in requests
                if r.employee_id in active_team and day in r.working_dates
            }
            if not active_team - away_on_day:
                result.append(
                    LeaveConflict(
                        code="MINIMUM_STAFFING",
                        blocking=False,
                        message="This absence may leave nobody available in the department. "
                        "Review team coverage.",
                    )
                )
                break
        if away:
            result.append(
                LeaveConflict(
                    code="TEAM_OVERLAP",
                    message=f"{len(away)} other team member(s) have overlapping "
                    "pending or approved leave.",
                    blocking=False,
                )
            )
    return result
