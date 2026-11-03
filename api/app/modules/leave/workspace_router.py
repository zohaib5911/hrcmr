"""Scoped balance projections, audited adjustments and a dated leave calendar."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction
from math import ceil
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.core.errors import AppError, NotFoundError
from app.core.rbac_matrix import Scope
from app.modules.companies.models import Company
from app.modules.employees.models import Employee, EmployeeAssignment
from app.modules.leave.calculations import year_bounds
from app.modules.leave.ledger import balance, calculate, lock_employee, move, reconcile
from app.modules.leave.models import LeaveLedger, LeaveType
from app.modules.leave.request_models import LeaveRequest
from app.modules.leave.workspace_schemas import (
    BalanceMoveIn,
    BalanceOut,
    BalancePage,
    CalendarEntry,
    CalendarOut,
)
from app.modules.rbac.deps import Access, require

router = APIRouter(tags=["leave"])
Balances = Annotated[Access, Depends(require("leave.balance.read"))]
Writes = Annotated[Access, Depends(require("leave.accrual.write"))]
Reads = Annotated[Access, Depends(require("leave.request.read"))]


async def _today(access: Access, on: date | None) -> date:
    if on is not None:
        return on
    company = (
        await access.db.execute(select(Company).where(Company.id == access.company_id))
    ).scalar_one()
    return datetime.now(ZoneInfo(company.timezone)).date()


async def _people(
    access: Access, employee_id: uuid.UUID | None, *, own: bool, offset: int, limit: int
) -> list[Employee]:
    query = select(Employee).order_by(Employee.last_name, Employee.first_name, Employee.id)
    if employee_id is not None:
        if not await access.can_reach(employee_id):
            raise NotFoundError
        query = query.where(Employee.id == employee_id)
    if own or access.scope is Scope.OWN:
        if access.employee_id is None:
            return []
        query = query.where(Employee.id == access.employee_id)
    elif access.scope is Scope.REPORTS:
        if access.employee_id is None:
            return []
        query = query.where(Employee.id.in_(await access.reports.reports_of(access.employee_id)))
    rows = list((await access.db.execute(query.offset(offset).limit(limit))).scalars())
    if employee_id is not None and not rows:
        raise NotFoundError
    return rows


async def _balances(access: Access, employee: Employee, on: date) -> list[BalanceOut]:
    company = (
        await access.db.execute(select(Company).where(Company.id == access.company_id))
    ).scalar_one()
    start, end = year_bounds(on, company.leave_year_start_month_day)
    kinds = list((await access.db.execute(select(LeaveType).order_by(LeaveType.name))).scalars())
    movements = list(
        (
            await access.db.execute(
                select(LeaveLedger).where(
                    LeaveLedger.employee_id == employee.id, LeaveLedger.leave_year_start == start
                )
            )
        ).scalars()
    )
    pending = list(
        (
            await access.db.execute(
                select(LeaveRequest).where(
                    LeaveRequest.employee_id == employee.id,
                    LeaveRequest.status == "pending",
                    LeaveRequest.start_date < end,
                    LeaveRequest.end_date >= start,
                )
            )
        ).scalars()
    )
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
        if kind.archived_at is None:
            try:
                calculated = await calculate(access.db, employee, kind, on)
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


@router.get("/leave-balances", response_model=BalancePage)
async def balances(
    access: Balances,
    on: date | None = None,
    employee_id: uuid.UUID | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> BalancePage:
    people = await _people(access, employee_id, own=False, offset=offset, limit=limit + 1)
    day = await _today(access, on)
    items = [row for person in people[:limit] for row in await _balances(access, person, day)]
    return BalancePage(items=items, next_offset=offset + limit if len(people) > limit else None)


@router.get("/leave-balances/own", response_model=BalancePage)
async def own_balances(access: Balances, on: date | None = None) -> BalancePage:
    people = await _people(access, None, own=True, offset=0, limit=1)
    day = await _today(access, on)
    return BalancePage(
        items=await _balances(access, people[0], day) if people else [], next_offset=None
    )


@router.get("/employees/{employee_id}/leave-balances", response_model=BalancePage)
async def employee_balances(
    employee_id: uuid.UUID, access: Balances, on: date | None = None
) -> BalancePage:
    people = await _people(access, employee_id, own=False, offset=0, limit=1)
    return BalancePage(
        items=await _balances(access, people[0], await _today(access, on)), next_offset=None
    )


async def _move(
    employee_id: uuid.UUID,
    body: BalanceMoveIn,
    access: Access,
    operation: Literal["grant", "deduct", "set"],
) -> BalancePage:
    if not await access.can_reach(employee_id):
        raise NotFoundError
    employee = await lock_employee(access.db, employee_id)
    existing = (
        await access.db.execute(
            select(LeaveLedger.id).where(LeaveLedger.idempotency_key == body.idempotency_key)
        )
    ).scalar_one_or_none()
    try:
        _, standard = await reconcile(access.db, employee_id, body.leave_type_id, body.on)
    except AppError as error:
        if error.code != "IRREGULAR_HOURS":
            raise
        standard = []
    company = (
        await access.db.execute(select(Company).where(Company.id == access.company_id))
    ).scalar_one()
    year, _ = year_bounds(body.on, company.leave_year_start_month_day)
    before = await balance(access.db, employee_id, body.leave_type_id, year)
    row = await move(
        access.db,
        employee_id,
        body.leave_type_id,
        year,
        operation=operation,
        days=body.days,
        reason=body.reason,
        key=body.idempotency_key,
    )
    if row is not None and (existing is None or standard):
        await access.audit(
            f"leave.balance_{operation}",
            entity_type="employee",
            entity_id=employee.id,
            before={"days": str(before)},
            after={
                "days": str(await balance(access.db, employee_id, body.leave_type_id, year)),
                "movement_id": str(row.id),
                "standard_movements": [str(r.id) for r in standard],
            },
            reason=body.reason.strip(),
        )
    await access.db.commit()
    return BalancePage(items=await _balances(access, employee, body.on), next_offset=None)


@router.post("/employees/{employee_id}/leave-balances/grant", response_model=BalancePage)
async def grant(employee_id: uuid.UUID, body: BalanceMoveIn, access: Writes) -> BalancePage:
    return await _move(employee_id, body, access, "grant")


@router.post("/employees/{employee_id}/leave-balances/deduct", response_model=BalancePage)
async def deduct(employee_id: uuid.UUID, body: BalanceMoveIn, access: Writes) -> BalancePage:
    return await _move(employee_id, body, access, "deduct")


@router.post("/employees/{employee_id}/leave-balances/set", response_model=BalancePage)
async def set_balance(employee_id: uuid.UUID, body: BalanceMoveIn, access: Writes) -> BalancePage:
    return await _move(employee_id, body, access, "set")


@router.get("/leave/calendar", response_model=CalendarOut)
async def calendar(
    access: Reads,
    month: Annotated[str, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")],
    department_id: uuid.UUID | None = None,
) -> CalendarOut:
    try:
        start = date.fromisoformat(month + "-01")
        end = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    except ValueError as error:
        raise AppError("VALIDATION_ERROR", "Choose a valid month.", status_code=422) from error
    query = (
        select(LeaveRequest, Employee, LeaveType)
        .join(Employee, Employee.id == LeaveRequest.employee_id)
        .join(LeaveType, LeaveType.id == LeaveRequest.leave_type_id)
        .where(
            LeaveRequest.status.in_(("pending", "approved")),
            LeaveRequest.start_date < end,
            LeaveRequest.end_date >= start,
        )
        .order_by(LeaveRequest.start_date, LeaveRequest.id)
    )
    if access.scope is Scope.OWN:
        query = query.where(Employee.id == access.employee_id)
    elif access.scope is Scope.REPORTS:
        reports = (
            await access.reports.reports_of(access.employee_id) if access.employee_id else set()
        )
        query = query.where(Employee.id.in_(reports))
    if department_id is not None:
        query = query.where(
            Employee.id.in_(
                select(EmployeeAssignment.employee_id).where(
                    EmployeeAssignment.department_id == department_id,
                    EmployeeAssignment.effective_from < end,
                    EmployeeAssignment.ended_at.is_(None) | (EmployeeAssignment.ended_at > start),
                )
            )
        )
    items = []
    for request, employee, kind in (await access.db.execute(query)).all():
        working = [
            date.fromisoformat(d)
            for d in request.working_dates
            if start.isoformat() <= d < end.isoformat()
        ]
        if working:
            items.append(
                CalendarEntry(
                    id=request.id,
                    employee_id=employee.id,
                    employee_name=f"{employee.first_name} {employee.last_name}",
                    leave_type_name=kind.name,
                    colour=kind.colour,
                    status=request.status,
                    working_dates=sorted(working),
                )
            )
    return CalendarOut(month=month, items=items)
