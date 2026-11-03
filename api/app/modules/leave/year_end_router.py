"""Read-only carry-over previews and atomic, repeatable audited company year closes."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.errors import AppError, ConflictError
from app.modules.companies.models import Company
from app.modules.employees.models import Employee
from app.modules.leave.calculations import year_bounds
from app.modules.leave.ledger import reconcile
from app.modules.leave.models import LeaveLedger, LeaveType
from app.modules.leave.projections import projected_balances
from app.modules.leave.request_models import LeaveRequest
from app.modules.leave.year_end_models import LeaveYearEndRun
from app.modules.leave.year_end_schemas import CarryRow, YearEndCommitIn, YearEndIn, YearEndPreview
from app.modules.rbac.deps import Access, require

router = APIRouter(prefix="/leave/year-end", tags=["leave"])
Writes = Annotated[Access, Depends(require("leave.accrual.write"))]
ZERO = Decimal("0.00")


def _today(company: Company) -> date:
    return datetime.now(ZoneInfo(company.timezone)).date()


async def _company(access: Access, *, lock: bool = False) -> Company:
    query = select(Company).where(Company.id == access.company_id)
    if lock:
        query = query.with_for_update()
    return (await access.db.execute(query)).scalar_one()


async def _existing(access: Access, start: date) -> LeaveYearEndRun | None:
    return (
        await access.db.execute(select(LeaveYearEndRun).where(LeaveYearEndRun.from_year == start))
    ).scalar_one_or_none()


def _input_overrides(body: YearEndIn) -> list[dict[str, object]]:
    return [
        o.model_dump(mode="json")
        for o in sorted(body.overrides, key=lambda o: (str(o.employee_id), str(o.leave_type_id)))
    ]


async def _preview(access: Access, body: YearEndIn, company: Company) -> YearEndPreview:
    start, end = year_bounds(body.from_year, company.leave_year_start_month_day)
    if start != body.from_year:
        raise AppError(
            "VALIDATION_ERROR",
            "Choose the configured leave-year start date.",
            status_code=422,
            field="from_year",
        )
    overrides = {(o.employee_id, o.leave_type_id): o for o in body.overrides}
    if len(overrides) != len(body.overrides) or any(not o.reason.strip() for o in body.overrides):
        raise AppError(
            "VALIDATION_ERROR",
            "Use one override per person and type, with a reason.",
            status_code=422,
        )
    kinds = {r.id: r for r in (await access.db.execute(select(LeaveType))).scalars()}
    people = list((await access.db.execute(select(Employee).order_by(Employee.id))).scalars())
    blockers = []
    if _today(company) < end:
        blockers.append(
            "This leave year has not ended yet. You can preview it now and commit after it ends."
        )
    if (
        await access.db.execute(
            select(LeaveRequest.id)
            .where(
                LeaveRequest.status == "pending",
                LeaveRequest.start_date < end,
                LeaveRequest.end_date >= start,
            )
            .limit(1)
        )
    ).first():
        blockers.append("Resolve pending requests in this leave year before committing.")
    rows = []
    seen = set()
    for employee in people:
        for balance in await projected_balances(access.db, employee, end - timedelta(days=1)):
            kind = kinds[balance.leave_type_id]
            key = (employee.id, kind.id)
            seen.add(key)
            override = overrides.get(key)
            remaining = balance.available
            limit = kind.carry_over_limit_days if kind.archived_at is None else ZERO
            carry = min(max(remaining or ZERO, ZERO), limit)
            if employee.leave_date is not None and employee.leave_date < end:
                carry = ZERO
                limit = ZERO
            if remaining is None:
                blockers.append(
                    f"{balance.employee_name} · {kind.name}: {balance.calculation_issue}"
                )
            elif remaining < 0 and kind.days_per_year is not None:
                blockers.append(
                    f"Review the negative {kind.name} balance for "
                    f"{balance.employee_name} before closing."
                )
            if override is not None:
                if remaining is None or override.days > max(remaining, ZERO):
                    raise AppError(
                        "VALIDATION_ERROR",
                        "Override carry-over cannot exceed the available positive balance.",
                        status_code=422,
                        field="days",
                    )
                if (
                    kind.archived_at is not None
                    or (employee.leave_date is not None and employee.leave_date < end)
                ) and override.days > 0:
                    raise AppError(
                        "VALIDATION_ERROR",
                        "Archived types and departed employees cannot carry leave forward.",
                        status_code=422,
                    )
                carry = override.days
            rows.append(
                CarryRow(
                    employee_id=employee.id,
                    employee_name=balance.employee_name,
                    leave_type_id=kind.id,
                    leave_type_name=kind.name,
                    remaining=remaining,
                    limit=limit,
                    carry=carry,
                    expire=max((remaining or ZERO) - carry, ZERO),
                    override_reason=override.reason.strip() if override else None,
                )
            )
    if overrides.keys() - seen:
        raise AppError(
            "VALIDATION_ERROR",
            "An override does not match a person and leave type in this company.",
            status_code=422,
        )
    snapshot = {
        "company_id": str(access.company_id),
        "from_year": start.isoformat(),
        "to_year": end.isoformat(),
        "rows": [r.model_dump(mode="json") for r in rows],
        "blockers": blockers,
        "input_overrides": _input_overrides(body),
    }
    token = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return YearEndPreview(
        from_year=start, to_year=end, rows=rows, blockers=blockers, preview_token=token
    )


@router.post("/preview", response_model=YearEndPreview)
async def preview(body: YearEndIn, access: Writes) -> YearEndPreview:
    existing = await _existing(access, body.from_year)
    if existing is not None:
        return YearEndPreview.model_validate(existing.overrides["preview"]).model_copy(
            update={"committed_run_id": existing.id}
        )
    return await _preview(access, body, await _company(access))


@router.post("/commit", response_model=YearEndPreview)
async def commit(body: YearEndCommitIn, access: Writes) -> YearEndPreview:
    company = await _company(access, lock=True)
    existing = await _existing(access, body.from_year)
    if existing is not None:
        if existing.preview_token != body.preview_token or existing.overrides[
            "input_overrides"
        ] != _input_overrides(body):
            raise ConflictError("This leave year has already been closed with a different review.")
        return YearEndPreview.model_validate(existing.overrides["preview"]).model_copy(
            update={"committed_run_id": existing.id}
        )
    # Match every balance writer's employee lock, in a stable order, before checking the snapshot.
    people = list(
        (
            await access.db.execute(select(Employee).order_by(Employee.id).with_for_update())
        ).scalars()
    )
    reviewed = await _preview(access, body, company)
    if reviewed.blockers:
        raise ConflictError(reviewed.blockers[0])
    if reviewed.preview_token != body.preview_token:
        raise ConflictError(
            "The leave balances or rules changed. Preview and review the year again."
        )
    target_closed = await _existing(access, reviewed.to_year)
    if target_closed is not None:
        raise ConflictError("The destination leave year is already closed.")
    run = LeaveYearEndRun(
        company_id=access.company_id,
        from_year=reviewed.from_year,
        to_year=reviewed.to_year,
        run_by=access.caller.user_id,
        preview_token=reviewed.preview_token,
        overrides={
            "preview": reviewed.model_dump(mode="json"),
            "input_overrides": _input_overrides(body),
        },
        committed_at=datetime.now(UTC),
    )
    # Add the close marker after reconciliation so ensure_open still admits closing-year movements.
    people_by_id = {p.id: p for p in people}
    for row in reviewed.rows:
        if row.remaining is None:
            raise ConflictError("A balance could not be calculated. Preview the year again.")
        kind = (
            await access.db.execute(select(LeaveType).where(LeaveType.id == row.leave_type_id))
        ).scalar_one()
        if kind.archived_at is None:
            try:
                await reconcile(
                    access.db,
                    row.employee_id,
                    row.leave_type_id,
                    reviewed.to_year - timedelta(days=1),
                )
            except AppError as error:
                if error.code != "IRREGULAR_HOURS":
                    raise
        if row.remaining > 0:
            access.db.add(
                LeaveLedger(
                    company_id=access.company_id,
                    employee_id=people_by_id[row.employee_id].id,
                    leave_type_id=row.leave_type_id,
                    leave_year_start=reviewed.from_year,
                    entry_type="year_end_expiry",
                    days=-row.remaining,
                    reason=(
                        f"Year-end close; carry {row.carry} days to {reviewed.to_year.isoformat()}"
                    ),
                )
            )
        if row.carry > 0:
            access.db.add(
                LeaveLedger(
                    company_id=access.company_id,
                    employee_id=row.employee_id,
                    leave_type_id=row.leave_type_id,
                    leave_year_start=reviewed.to_year,
                    entry_type="carry_over",
                    days=row.carry,
                    reason=row.override_reason
                    or f"Standard carry-over from {reviewed.from_year.isoformat()}",
                )
            )
    access.db.add(run)
    await access.db.flush()
    await access.audit(
        "leave.year_end_committed",
        entity_type="leave_year_end_run",
        entity_id=run.id,
        after={
            "from_year": reviewed.from_year.isoformat(),
            "to_year": reviewed.to_year.isoformat(),
            "people": len(people),
            "carry_days": str(sum((r.carry for r in reviewed.rows), ZERO)),
        },
    )
    await access.db.commit()
    return reviewed.model_copy(update={"committed_run_id": run.id})
