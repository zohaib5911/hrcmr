"""Permission-gated salary history and preview; no salary is included in profile responses."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.errors import ConflictError, NotFoundError
from app.modules.employees.compensation_schemas import (
    CompensationHistory,
    CompensationIn,
    CompensationOut,
    WageCheck,
)
from app.modules.employees.employment_router import _locked_employee
from app.modules.employees.minimum_wage import wage_check
from app.modules.employees.models import EmployeeCompensation
from app.modules.employees.router import _employee as reachable_employee
from app.modules.pay.models import PayBand, PaymentType, PaySchedule, TaxCode
from app.modules.rbac.deps import Access, require

router = APIRouter(tags=["employees"])
Reads = Annotated[Access, Depends(require("employee.compensation.read"))]
Writes = Annotated[Access, Depends(require("employee.compensation.write"))]


async def _out(access: Access, row: EmployeeCompensation) -> CompensationOut:
    result = CompensationOut.model_validate(row)
    for field, model, ident, column in (
        ("tax_code", TaxCode, row.tax_code_id, TaxCode.code),
        ("payment_type", PaymentType, row.payment_type_id, PaymentType.name),
        ("pay_band", PayBand, row.pay_band_id, PayBand.name),
        ("pay_schedule", PaySchedule, row.pay_schedule_id, PaySchedule.name),
    ):
        if ident:
            value = (
                await access.db.execute(select(column).where(model.id == ident))
            ).scalar_one_or_none()
            setattr(result, field, value)
    return result


@router.get("/employees/{employee_id}/compensation", response_model=CompensationHistory)
async def compensation_history(employee_id: uuid.UUID, access: Reads) -> CompensationHistory:
    await reachable_employee(access, employee_id)
    rows = list(
        (
            await access.db.execute(
                select(EmployeeCompensation)
                .where(EmployeeCompensation.employee_id == employee_id)
                .order_by(
                    EmployeeCompensation.effective_from.desc(), EmployeeCompensation.id.desc()
                )
            )
        ).scalars()
    )
    records = [await _out(access, row) for row in rows]
    current = next((r for r in records if r.effective_from <= datetime.now(UTC).date()), None)
    return CompensationHistory(current=current, records=records)


@router.post("/employees/{employee_id}/compensation/check", response_model=WageCheck)
async def check_wage(employee_id: uuid.UUID, body: CompensationIn, access: Writes) -> WageCheck:
    employee = await reachable_employee(access, employee_id)
    if body.effective_from < employee.hire_date:
        raise ConflictError("The salary cannot start before the hire date.", field="effective_from")
    return wage_check(body, employee.date_of_birth)


@router.post(
    "/employees/{employee_id}/compensation", status_code=201, response_model=CompensationOut
)
async def add_compensation(
    employee_id: uuid.UUID, body: CompensationIn, access: Writes
) -> CompensationOut:
    employee = await _locked_employee(access, employee_id)
    if body.effective_from < employee.hire_date:
        raise ConflictError("The salary cannot start before the hire date.", field="effective_from")
    for model, ident in (
        (TaxCode, body.tax_code_id),
        (PaymentType, body.payment_type_id),
        (PayBand, body.pay_band_id),
        (PaySchedule, body.pay_schedule_id),
    ):
        if (
            ident
            and (
                await access.db.execute(
                    select(model.id).where(model.id == ident, model.archived_at.is_(None))
                )
            ).scalar_one_or_none()
            is None
        ):
            raise NotFoundError
    existing = (
        await access.db.execute(
            select(EmployeeCompensation.id).where(
                EmployeeCompensation.employee_id == employee.id,
                EmployeeCompensation.effective_from == body.effective_from,
            )
        )
    ).first()
    if existing:
        raise ConflictError("A salary record already starts on this date.", field="effective_from")
    row = EmployeeCompensation(
        company_id=access.company_id, employee_id=employee.id, **body.model_dump()
    )
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "employee.compensation_added",
        entity_type="employee",
        entity_id=employee.id,
        after=body.model_dump(mode="json"),
    )
    await access.db.commit()
    return await _out(access, row)
