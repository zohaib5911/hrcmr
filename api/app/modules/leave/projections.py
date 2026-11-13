"""Read-only allowances shared by leave workspaces and year-end review."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from fractions import Fraction
from math import ceil
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.core.errors import AppError
from app.modules.companies.models import Company
from app.modules.leave.calculations import year_bounds
from app.modules.leave.ledger import calculate
from app.modules.leave.models import LeaveLedger, LeaveType
from app.modules.leave.request_models import LeaveRequest
from app.modules.leave.workspace_schemas import BalanceOut
from app.modules.leave.year_end_models import LeaveYearEndRun

if TYPE_CHECKING:
    from datetime import date

    from app.db.session import TenantSession
    from app.modules.employees.models import Employee


async def projected_balances(db: TenantSession, employee: Employee, on: date) -> list[BalanceOut]:
    return await projected_balances_for_people(db, [employee], on)


async def projected_balances_for_people(
    db: TenantSession, employees: list[Employee], on: date
) -> list[BalanceOut]:
    """Load shared settings and page-scoped ledger/request rows once per balance page."""
    if not employees:
        return []
    company = (await db.execute(select(Company).where(Company.id == db.company_id))).scalar_one()
    start, end = year_bounds(on, company.leave_year_start_month_day)
    closed = (
        await db.execute(select(LeaveYearEndRun.id).where(LeaveYearEndRun.from_year == start))
    ).scalar_one_or_none() is not None
    kinds = list((await db.execute(select(LeaveType).order_by(LeaveType.name))).scalars())
    movements = list(
        (
            await db.execute(
                select(LeaveLedger).where(
                    LeaveLedger.employee_id.in_([employee.id for employee in employees]),
                    LeaveLedger.leave_year_start == start,
                )
            )
        ).scalars()
    )
    pending = list(
        (
            await db.execute(
                select(LeaveRequest).where(
                    LeaveRequest.employee_id.in_([employee.id for employee in employees]),
                    LeaveRequest.status == "pending",
                    LeaveRequest.start_date < end,
                    LeaveRequest.end_date >= start,
                )
            )
        ).scalars()
    )
    movements_by_employee = defaultdict(list)
    for movement in movements:
        movements_by_employee[movement.employee_id].append(movement)
    pending_by_employee = defaultdict(list)
    for request in pending:
        pending_by_employee[request.employee_id].append(request)
    result = []
    for employee in employees:
        result.extend(
            await _project_employee(
                db,
                employee,
                on,
                start,
                end,
                closed,
                kinds,
                movements_by_employee[employee.id],
                pending_by_employee[employee.id],
            )
        )
    return result


async def _project_employee(
    db: TenantSession,
    employee: Employee,
    on: date,
    start: date,
    end: date,
    closed: bool,
    kinds: list[LeaveType],
    movements: list[LeaveLedger],
    pending: list[LeaveRequest],
) -> list[BalanceOut]:
    # The request snapshot retains exact fractions; use the same rounding as request planning.
    result = []
    for kind in kinds:
        entries = [r for r in movements if r.leave_type_id == kind.id]
        if kind.archived_at is not None and not entries:
            continue
        current = sum((r.days for r in entries), Decimal(0))
        available: Decimal | None = current
        entitlement: Decimal | None = None
        calendar_days: Decimal | None = None
        issue: str | None = None
        if kind.archived_at is None and not closed:
            try:
                calculated = await calculate(db, employee, kind, on)
                entitlement = calculated.entitlement
                calendar_days = calculated.calendar_days
                for bucket, target in (("entitlement", entitlement), ("calendar", -calendar_days)):
                    if target is not None:
                        available = (
                            (available or Decimal(0))
                            + target
                            - sum((r.days for r in entries if r.bucket == bucket), Decimal(0))
                        )
            except AppError as error:
                issue = error.message
                if error.code != "IRREGULAR_HOURS":
                    available = None
        requested = sum(
            (
                Decimal(
                    ceil(
                        sum(
                            (
                                Fraction(q)
                                for day, q in r.working_dates.items()
                                if start.isoformat() <= day < end.isoformat()
                            ),
                            Fraction(0),
                        )
                        * 100
                    )
                )
                / 100
                for r in pending
                if r.leave_type_id == kind.id
            ),
            Decimal(0),
        )
        result.append(
            BalanceOut(
                employee_id=employee.id,
                employee_name=f"{employee.first_name} {employee.last_name}",
                leave_type_id=kind.id,
                leave_type_name=kind.name,
                colour=kind.colour,
                leave_year_start=start,
                ledger_balance=current.quantize(Decimal("0.01")),
                available=available.quantize(Decimal("0.01")) if available is not None else None,
                entitlement=entitlement.quantize(Decimal("0.01"))
                if entitlement is not None
                else None,
                calendar_days=calendar_days.quantize(Decimal("0.01"))
                if calendar_days is not None
                else None,
                taken=-sum((r.days for r in entries if r.entry_type == "taken"), Decimal(0)),
                pending=requested,
                calculation_issue=issue,
            )
        )
    return result
