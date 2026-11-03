"""Transactional leave movements; callers commit the movement and audit together.

The employee row serializes every writer for a balance. Reads never grant leave.
Managed entitlement/calendar buckets are reconciled with deltas, preserving history
and manual movements when employment terms or calendars are corrected.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from sqlalchemy import func, select

from app.core.errors import AppError, ConflictError, NotFoundError
from app.modules.companies.models import Company
from app.modules.employees.models import Employee, EmployeeAssignment
from app.modules.holidays.models import BankHoliday, CompanyHoliday, WorkingPatternDay
from app.modules.leave.calculations import (
    ZERO,
    Pattern,
    calendar_deductions,
    dates,
    entitlement,
    standard_day,
    year_bounds,
)
from app.modules.leave.models import LeaveLedger, LeaveType

if TYPE_CHECKING:
    import uuid

    from app.db.session import TenantSession


@dataclass(frozen=True)
class Calculation:
    year_start: date
    year_end: date
    entitlement: Decimal | None
    calendar_days: Decimal
    standard_day_hours: Decimal


async def lock_employee(db: TenantSession, employee_id: uuid.UUID) -> Employee:
    employee = (
        await db.execute(select(Employee).where(Employee.id == employee_id).with_for_update())
    ).scalar_one_or_none()
    if employee is None:
        raise NotFoundError
    return employee


async def leave_type(db: TenantSession, type_id: uuid.UUID) -> LeaveType:
    row = (
        await db.execute(
            select(LeaveType).where(LeaveType.id == type_id, LeaveType.archived_at.is_(None))
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return row


async def balance(
    db: TenantSession,
    employee_id: uuid.UUID,
    type_id: uuid.UUID,
    year: date,
    *,
    bucket: str | None = None,
) -> Decimal:
    query = select(func.coalesce(func.sum(LeaveLedger.days), 0)).where(
        LeaveLedger.employee_id == employee_id,
        LeaveLedger.leave_type_id == type_id,
        LeaveLedger.leave_year_start == year,
    )
    if bucket is not None:
        query = query.where(LeaveLedger.bucket == bucket)
    return Decimal((await db.execute(query)).scalar_one())


def validate_days(days: Decimal, *, positive: bool) -> None:
    if (
        not days.is_finite()
        or abs(days) > Decimal("999999.99")
        or days != days.quantize(Decimal("0.01"))
        or (positive and days <= 0)
    ):
        raise AppError(
            "VALIDATION_ERROR",
            "Enter a valid day amount with up to two decimal places.",
            status_code=422,
            field="days",
        )


async def move(
    db: TenantSession,
    employee_id: uuid.UUID,
    type_id: uuid.UUID,
    year: date,
    *,
    operation: Literal["grant", "deduct", "set"],
    days: Decimal,
    reason: str,
    key: uuid.UUID,
) -> LeaveLedger | None:
    employee = await lock_employee(db, employee_id)
    await leave_type(db, type_id)
    validate_days(days, positive=operation != "set")
    if not reason.strip() or len(reason) > 1000:
        raise AppError(
            "VALIDATION_ERROR",
            "Give a reason (up to 1000 characters).",
            status_code=422,
            field="reason",
        )
    company = (await db.execute(select(Company).where(Company.id == db.company_id))).scalar_one()
    if year_bounds(year, company.leave_year_start_month_day)[0] != year:
        raise AppError(
            "VALIDATION_ERROR",
            "Choose the start of a configured leave year.",
            status_code=422,
            field="leave_year_start",
        )
    previous = (
        await db.execute(select(LeaveLedger).where(LeaveLedger.idempotency_key == key))
    ).scalar_one_or_none()
    if previous is not None:
        expected = days if operation == "grant" else -days
        if (
            previous.employee_id != employee_id
            or previous.leave_type_id != type_id
            or previous.leave_year_start != year
            or previous.entry_type != operation
            or previous.reason != reason.strip()
            or (operation != "set" and previous.days != expected)
            or (operation == "set" and previous.target_days != days)
        ):
            raise ConflictError("This operation key has already been used for a different change.")
        return previous
    current = await balance(db, employee_id, type_id, year)
    delta = days - current if operation == "set" else days if operation == "grant" else -days
    if not company.allow_negative_leave_balance and current + delta < 0:
        raise ConflictError("This change would make the leave balance negative.", field="days")
    row = LeaveLedger(
        company_id=employee.company_id,
        employee_id=employee_id,
        leave_type_id=type_id,
        leave_year_start=year,
        entry_type=operation,
        days=delta,
        reason=reason.strip(),
        idempotency_key=key,
        target_days=days if operation == "set" else None,
    )
    db.add(row)
    await db.flush()
    return row


async def calculate(
    db: TenantSession, employee: Employee, kind: LeaveType, on: date
) -> Calculation:
    company = (await db.execute(select(Company).where(Company.id == db.company_id))).scalar_one()
    start, end = year_bounds(on, company.leave_year_start_month_day)
    default, patterns = await working_pattern(db, employee.id, start, end)
    grant = entitlement(
        kind.days_per_year,
        start,
        end,
        employee.hire_date,
        employee.leave_date,
        default,
        patterns,
        method="monthly" if kind.accrual_method == "monthly" else "front_loaded",
        as_of=on,
    )
    # Seeded Annual Leave receives closures; other types can opt into bank holidays.
    bank: frozenset[date] = frozenset()
    if kind.bank_holidays_included and company.bank_holidays_non_working:
        holidays = (
            (
                await db.execute(
                    select(BankHoliday).where(
                        BankHoliday.region == company.bank_holiday_region,
                        BankHoliday.on_date >= start,
                        BankHoliday.on_date < end,
                    )
                )
            )
            .scalars()
            .all()
        )
        needed_start = max(start, employee.hire_date)
        needed_end = min(
            end, employee.leave_date + timedelta(days=1) if employee.leave_date else end
        )
        needed_years = {d.year for d in dates(needed_start, needed_end)}
        if not needed_years <= {h.on_date.year for h in holidays}:
            raise AppError(
                "BANK_HOLIDAYS_UNAVAILABLE",
                "The official regional bank-holiday calendar does not cover this leave year yet.",
                status_code=503,
            )
        bank = frozenset(h.on_date for h in holidays)
    closures: frozenset[date] = frozenset()
    if kind.seed_key == "annual":
        shutdowns = (
            (
                await db.execute(
                    select(CompanyHoliday).where(
                        CompanyHoliday.archived_at.is_(None),
                        CompanyHoliday.deduct_from_annual_leave.is_(True),
                        CompanyHoliday.start_date < end,
                        CompanyHoliday.end_date >= start,
                    )
                )
            )
            .scalars()
            .all()
        )
        closures = frozenset(
            d
            for c in shutdowns
            for d in dates(max(start, c.start_date), min(end, c.end_date + timedelta(days=1)))
        )
    deductions = calendar_deductions(
        start,
        end,
        employee.hire_date,
        employee.leave_date,
        default,
        patterns,
        bank,
        closures,
        bank_holidays_included=kind.bank_holidays_included,
        bank_holidays_non_working=company.bank_holidays_non_working,
    )
    return Calculation(start, end, grant, deductions, standard_day(default))


async def reconcile(
    db: TenantSession, employee_id: uuid.UUID, type_id: uuid.UUID, on: date
) -> tuple[Calculation, list[LeaveLedger]]:
    employee = await lock_employee(db, employee_id)
    kind = await leave_type(db, type_id)
    calculated = await calculate(db, employee, kind, on)
    result = []
    for bucket, target in (
        ("entitlement", calculated.entitlement),
        ("calendar", -calculated.calendar_days),
    ):
        if target is None:
            continue
        previous = await balance(db, employee_id, type_id, calculated.year_start, bucket=bucket)
        delta = target - previous
        if delta == 0:
            continue
        entry = (
            ("accrual" if kind.accrual_method == "monthly" else "grant")
            if bucket == "entitlement" and delta > 0
            else "adjustment"
        )
        row = LeaveLedger(
            company_id=employee.company_id,
            employee_id=employee_id,
            leave_type_id=type_id,
            leave_year_start=calculated.year_start,
            entry_type=entry,
            days=delta,
            bucket=bucket,
            reason=f"Standard {bucket} recalculated as of {on.isoformat()}",
        )
        db.add(row)
        result.append(row)
    await db.flush()
    return calculated, result


async def working_pattern(
    db: TenantSession,
    employee_id: uuid.UUID,
    start: date,
    end: date,
    *,
    regular_only: bool = True,
) -> tuple[tuple[Decimal, ...], tuple[Pattern, ...]]:
    rows = (
        (await db.execute(select(WorkingPatternDay).order_by(WorkingPatternDay.weekday)))
        .scalars()
        .all()
    )
    by_day = {r.weekday: r.hours if r.is_working else ZERO for r in rows}
    default = tuple(by_day.get(i, ZERO) for i in range(1, 8))
    assignments = (
        (
            await db.execute(
                select(EmployeeAssignment)
                .where(
                    EmployeeAssignment.employee_id == employee_id,
                    EmployeeAssignment.effective_from < end,
                    (EmployeeAssignment.ended_at.is_(None) | (EmployeeAssignment.ended_at > start)),
                )
                .order_by(EmployeeAssignment.effective_from)
            )
        )
        .scalars()
        .all()
    )
    if regular_only and any(a.employment_type in ("zero_hours", "casual") for a in assignments):
        raise AppError(
            "IRREGULAR_HOURS",
            "Use a reviewed manual grant for irregular hours; "
            "regular-pattern entitlement cannot be applied.",
            status_code=422,
        )
    if not regular_only and any(
        a.employment_type in ("zero_hours", "casual") and a.custom_working_days is None
        for a in assignments
    ):
        raise AppError(
            "WORKING_PATTERN_REQUIRED",
            "Set a personal working pattern before requesting leave "
            "for an irregular-hours employee.",
            status_code=422,
        )
    names = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
    patterns = tuple(
        Pattern(
            a.effective_from,
            a.ended_at,
            tuple(
                (a.hours_per_day or default[i] or standard_day(default))
                if name in a.custom_working_days
                else ZERO
                for i, name in enumerate(names)
            )
            if a.custom_working_days is not None
            else tuple(
                (a.hours_per_day if a.hours_per_day is not None else h) if h > 0 else ZERO
                for h in default
            ),
        )
        for a in assignments
    )
    return default, patterns
