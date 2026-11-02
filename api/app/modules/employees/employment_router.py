"""Employment tab: audited changes, append-only role history and supporting records."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.core.errors import ConflictError, NotFoundError
from app.modules.companies.models import Department, Designation, Location
from app.modules.employees.employment_schemas import (
    AssignmentIn,
    AssignmentOut,
    EducationIn,
    EducationOut,
    EmploymentTab,
    HireDateIn,
    MembershipIn,
    MembershipOut,
    PreviousEmploymentIn,
    PreviousEmploymentOut,
    ResponsibilityIn,
    ResponsibilityOut,
    TrainingIn,
    TrainingOut,
)
from app.modules.employees.models import (
    Employee,
    EmployeeAssignment,
    EmployeeCompensation,
    EmployeeEducation,
    EmployeeMembership,
    EmployeePreviousEmployment,
    EmployeeResponsibility,
    EmployeeTrainingRecord,
)
from app.modules.employees.router import _employee as reachable_employee
from app.modules.employees.schemas import twelve_months_from
from app.modules.rbac.deps import Access, require

router = APIRouter(tags=["employees"])
Reads = Annotated[Access, Depends(require("employee.profile.read"))]
Writes = Annotated[Access, Depends(require("employee.org_assignment.write"))]


async def _locked_employee(access: Access, employee_id: uuid.UUID) -> Employee:
    await reachable_employee(access, employee_id)
    return (
        await access.db.execute(
            select(Employee).where(Employee.id == employee_id).with_for_update()
        )
    ).scalar_one()


async def _assignment_out(access: Access, row: EmployeeAssignment) -> AssignmentOut:
    result = AssignmentOut.model_validate(row)
    for field, model, ident, column in (
        ("department", Department, row.department_id, Department.name),
        ("designation", Designation, row.designation_id, Designation.title),
        ("location", Location, row.location_id, Location.name),
    ):
        if ident:
            setattr(
                result,
                field,
                (
                    await access.db.execute(select(column).where(model.id == ident))
                ).scalar_one_or_none(),
            )
    for field, ident in (
        ("reporting_authority", row.reporting_authority_employee_id),
        ("leave_sanctioning_authority", row.leave_sanctioning_employee_id),
    ):
        if ident:
            person = (
                await access.db.execute(select(Employee).where(Employee.id == ident))
            ).scalar_one_or_none()
            if person:
                setattr(result, field, f"{person.first_name} {person.last_name}")
    return result


@router.get("/employees/{employee_id}/employment", response_model=EmploymentTab)
async def employment_tab(employee_id: uuid.UUID, access: Reads) -> EmploymentTab:
    employee = await reachable_employee(access, employee_id)
    assignments = (
        await access.db.execute(
            select(EmployeeAssignment)
            .where(EmployeeAssignment.employee_id == employee.id)
            .order_by(EmployeeAssignment.effective_from.desc())
        )
    ).scalars()
    responsibilities = (
        await access.db.execute(
            select(EmployeeResponsibility)
            .where(EmployeeResponsibility.employee_id == employee.id)
            .order_by(EmployeeResponsibility.sort, EmployeeResponsibility.id)
        )
    ).scalars()
    previous = (
        await access.db.execute(
            select(EmployeePreviousEmployment).where(
                EmployeePreviousEmployment.employee_id == employee.id
            )
        )
    ).scalar_one_or_none()
    education = (
        await access.db.execute(
            select(EmployeeEducation)
            .where(EmployeeEducation.employee_id == employee.id)
            .order_by(EmployeeEducation.created_at, EmployeeEducation.id)
        )
    ).scalars()
    training = (
        await access.db.execute(
            select(EmployeeTrainingRecord)
            .where(EmployeeTrainingRecord.employee_id == employee.id)
            .order_by(EmployeeTrainingRecord.created_at, EmployeeTrainingRecord.id)
        )
    ).scalars()
    memberships = (
        await access.db.execute(
            select(EmployeeMembership)
            .where(EmployeeMembership.employee_id == employee.id)
            .order_by(EmployeeMembership.created_at, EmployeeMembership.id)
        )
    ).scalars()
    return EmploymentTab(
        hire_date=employee.hire_date,
        assignments=[await _assignment_out(access, r) for r in assignments],
        responsibilities=[ResponsibilityOut.model_validate(r) for r in responsibilities],
        previous_employment=PreviousEmploymentOut.model_validate(previous) if previous else None,
        education=[EducationOut.model_validate(r) for r in education],
        training=[TrainingOut.model_validate(r) for r in training],
        memberships=[MembershipOut.model_validate(r) for r in memberships],
    )


@router.put("/employees/{employee_id}/hire-date", status_code=204)
async def change_hire_date(employee_id: uuid.UUID, body: HireDateIn, access: Writes) -> None:
    employee = await _locked_employee(access, employee_id)
    if not body.reason.strip():
        raise ConflictError("Enter a reason.", field="reason")
    if body.hire_date > twelve_months_from(datetime.now(UTC).date()):
        raise ConflictError("The hire date cannot be more than 12 months ahead.", field="hire_date")
    for model in (EmployeeAssignment, EmployeeCompensation):
        first = (
            await access.db.execute(
                select(func.min(model.effective_from)).where(model.employee_id == employee.id)
            )
        ).scalar_one()
        if first and first < body.hire_date:
            raise ConflictError("An existing record starts before this date.", field="hire_date")
    before = employee.hire_date
    employee.hire_date = body.hire_date
    await access.audit(
        "employee.hire_date_changed",
        entity_type="employee",
        entity_id=employee.id,
        before={"hire_date": before.isoformat()},
        after={"hire_date": body.hire_date.isoformat(), "reason": body.reason.strip()},
    )
    await access.db.commit()


@router.post("/employees/{employee_id}/assignments", status_code=201, response_model=AssignmentOut)
async def change_role(employee_id: uuid.UUID, body: AssignmentIn, access: Writes) -> AssignmentOut:
    employee = await _locked_employee(access, employee_id)
    if body.effective_from < employee.hire_date:
        raise ConflictError("The role cannot start before the hire date.", field="effective_from")
    # Hierarchy levels are introduced in Phase 9. Never accept an unvalidated identifier.
    if body.organogram_level_id is not None:
        raise ConflictError("Hierarchy levels are not available yet.", field="organogram_level_id")
    for model, ident in (
        (Department, body.department_id),
        (Designation, body.designation_id),
        (Location, body.location_id),
    ):
        if ident is not None:
            row = (
                await access.db.execute(
                    select(model).where(model.id == ident, model.archived_at.is_(None))
                )
            ).scalar_one_or_none()
            if row is None:
                raise NotFoundError
            if isinstance(row, Designation) and row.department_id != body.department_id:
                raise ConflictError(
                    "Choose a designation in this department.", field="designation_id"
                )
    history = list(
        (
            await access.db.execute(
                select(EmployeeAssignment)
                .where(EmployeeAssignment.employee_id == employee.id)
                .order_by(EmployeeAssignment.effective_from)
            )
        ).scalars()
    )
    if history and body.effective_from <= history[-1].effective_from:
        raise ConflictError(
            "Choose a date after the latest role's start date.", field="effective_from"
        )
    # Validate each reporting chain at every change boundary affected by the new role.
    boundaries = set(
        (
            await access.db.execute(
                select(EmployeeAssignment.effective_from).where(
                    EmployeeAssignment.effective_from >= body.effective_from
                )
            )
        ).scalars()
    ) | {body.effective_from}
    for field in ("reporting_authority_employee_id", "leave_sanctioning_employee_id"):
        manager = getattr(body, field)
        if manager is None:
            continue
        if (
            await access.db.execute(
                select(Employee.id).where(Employee.id == manager, Employee.status != "archived")
            )
        ).scalar_one_or_none() is None:
            raise NotFoundError
        for day in boundaries:
            seen = {employee.id}
            cursor = manager
            while cursor is not None:
                if cursor in seen:
                    raise ConflictError("This reporting line would create a loop.", field=field)
                seen.add(cursor)
                cursor = (
                    await access.db.execute(
                        select(getattr(EmployeeAssignment, field))
                        .where(
                            EmployeeAssignment.employee_id == cursor,
                            EmployeeAssignment.effective_from <= day,
                        )
                        .order_by(EmployeeAssignment.effective_from.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
    if history:
        history[-1].ended_at = body.effective_from
        await access.db.flush()
    row = EmployeeAssignment(
        company_id=access.company_id, employee_id=employee.id, **body.model_dump()
    )
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "employee.role_changed",
        entity_type="employee",
        entity_id=employee.id,
        after=body.model_dump(mode="json"),
    )
    await access.db.commit()
    return await _assignment_out(access, row)


@router.put("/employees/{employee_id}/previous-employment", response_model=PreviousEmploymentOut)
async def previous_employment(
    employee_id: uuid.UUID, body: PreviousEmploymentIn, access: Writes
) -> PreviousEmploymentOut:
    employee = await _locked_employee(access, employee_id)
    row = (
        await access.db.execute(
            select(EmployeePreviousEmployment).where(
                EmployeePreviousEmployment.employee_id == employee.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = EmployeePreviousEmployment(company_id=access.company_id, employee_id=employee.id)
        access.db.add(row)
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    await access.db.flush()
    await access.audit(
        "employee.previous_employment_changed",
        entity_type="employee",
        entity_id=employee.id,
        after=body.model_dump(mode="json"),
    )
    await access.db.commit()
    return PreviousEmploymentOut.model_validate(row)


@router.post(
    "/employees/{employee_id}/responsibilities", status_code=201, response_model=ResponsibilityOut
)
async def add_responsibility(
    employee_id: uuid.UUID, body: ResponsibilityIn, access: Writes
) -> ResponsibilityOut:
    employee = await _locked_employee(access, employee_id)
    row = EmployeeResponsibility(
        company_id=access.company_id, employee_id=employee.id, **body.model_dump()
    )
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "employee.responsibility_added",
        entity_type="employee",
        entity_id=employee.id,
        after=body.model_dump(mode="json"),
    )
    await access.db.commit()
    return ResponsibilityOut.model_validate(row)


@router.put(
    "/employees/{employee_id}/responsibilities/{record_id}", response_model=ResponsibilityOut
)
async def change_responsibility(
    employee_id: uuid.UUID, record_id: uuid.UUID, body: ResponsibilityIn, access: Writes
) -> ResponsibilityOut:
    employee = await _locked_employee(access, employee_id)
    row = (
        await access.db.execute(
            select(EmployeeResponsibility).where(
                EmployeeResponsibility.id == record_id,
                EmployeeResponsibility.employee_id == employee.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    await access.audit(
        "employee.responsibility_changed",
        entity_type="employee",
        entity_id=employee.id,
        after=body.model_dump(mode="json"),
    )
    await access.db.commit()
    return ResponsibilityOut.model_validate(row)


@router.delete("/employees/{employee_id}/responsibilities/{record_id}", status_code=204)
async def remove_responsibility(
    employee_id: uuid.UUID, record_id: uuid.UUID, access: Writes
) -> None:
    employee = await _locked_employee(access, employee_id)
    row = (
        await access.db.execute(
            select(EmployeeResponsibility).where(
                EmployeeResponsibility.id == record_id,
                EmployeeResponsibility.employee_id == employee.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    await access.audit(
        "employee.responsibility_removed",
        entity_type="employee",
        entity_id=employee.id,
        before={"id": str(row.id)},
    )
    await access.db.delete(row)
    await access.db.commit()


@router.post("/employees/{employee_id}/education", status_code=201, response_model=EducationOut)
async def add_education(employee_id: uuid.UUID, body: EducationIn, access: Writes) -> EducationOut:
    employee = await _locked_employee(access, employee_id)
    row = EmployeeEducation(
        company_id=access.company_id, employee_id=employee.id, **body.model_dump()
    )
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "employee.education_added",
        entity_type="employee",
        entity_id=employee.id,
        after=body.model_dump(mode="json"),
    )
    await access.db.commit()
    return EducationOut.model_validate(row)


@router.put("/employees/{employee_id}/education/{record_id}", response_model=EducationOut)
async def change_education(
    employee_id: uuid.UUID, record_id: uuid.UUID, body: EducationIn, access: Writes
) -> EducationOut:
    employee = await _locked_employee(access, employee_id)
    row = (
        await access.db.execute(
            select(EmployeeEducation).where(
                EmployeeEducation.id == record_id, EmployeeEducation.employee_id == employee.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    await access.audit(
        "employee.education_changed",
        entity_type="employee",
        entity_id=employee.id,
        after=body.model_dump(mode="json"),
    )
    await access.db.commit()
    return EducationOut.model_validate(row)


@router.delete("/employees/{employee_id}/education/{record_id}", status_code=204)
async def remove_education(employee_id: uuid.UUID, record_id: uuid.UUID, access: Writes) -> None:
    employee = await _locked_employee(access, employee_id)
    row = (
        await access.db.execute(
            select(EmployeeEducation).where(
                EmployeeEducation.id == record_id, EmployeeEducation.employee_id == employee.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    await access.audit(
        "employee.education_removed",
        entity_type="employee",
        entity_id=employee.id,
        before={"id": str(row.id)},
    )
    await access.db.delete(row)
    await access.db.commit()


@router.post("/employees/{employee_id}/training", status_code=201, response_model=TrainingOut)
async def add_training(employee_id: uuid.UUID, body: TrainingIn, access: Writes) -> TrainingOut:
    employee = await _locked_employee(access, employee_id)
    row = EmployeeTrainingRecord(
        company_id=access.company_id, employee_id=employee.id, **body.model_dump()
    )
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "employee.training_added",
        entity_type="employee",
        entity_id=employee.id,
        after=body.model_dump(mode="json"),
    )
    await access.db.commit()
    return TrainingOut.model_validate(row)


@router.put("/employees/{employee_id}/training/{record_id}", response_model=TrainingOut)
async def change_training(
    employee_id: uuid.UUID, record_id: uuid.UUID, body: TrainingIn, access: Writes
) -> TrainingOut:
    employee = await _locked_employee(access, employee_id)
    row = (
        await access.db.execute(
            select(EmployeeTrainingRecord).where(
                EmployeeTrainingRecord.id == record_id,
                EmployeeTrainingRecord.employee_id == employee.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    await access.audit(
        "employee.training_changed",
        entity_type="employee",
        entity_id=employee.id,
        after=body.model_dump(mode="json"),
    )
    await access.db.commit()
    return TrainingOut.model_validate(row)


@router.delete("/employees/{employee_id}/training/{record_id}", status_code=204)
async def remove_training(employee_id: uuid.UUID, record_id: uuid.UUID, access: Writes) -> None:
    employee = await _locked_employee(access, employee_id)
    row = (
        await access.db.execute(
            select(EmployeeTrainingRecord).where(
                EmployeeTrainingRecord.id == record_id,
                EmployeeTrainingRecord.employee_id == employee.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    await access.audit(
        "employee.training_removed",
        entity_type="employee",
        entity_id=employee.id,
        before={"id": str(row.id)},
    )
    await access.db.delete(row)
    await access.db.commit()


@router.post("/employees/{employee_id}/memberships", status_code=201, response_model=MembershipOut)
async def add_membership(
    employee_id: uuid.UUID, body: MembershipIn, access: Writes
) -> MembershipOut:
    employee = await _locked_employee(access, employee_id)
    row = EmployeeMembership(
        company_id=access.company_id, employee_id=employee.id, **body.model_dump()
    )
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "employee.membership_added",
        entity_type="employee",
        entity_id=employee.id,
        after=body.model_dump(mode="json"),
    )
    await access.db.commit()
    return MembershipOut.model_validate(row)


@router.put("/employees/{employee_id}/memberships/{record_id}", response_model=MembershipOut)
async def change_membership(
    employee_id: uuid.UUID, record_id: uuid.UUID, body: MembershipIn, access: Writes
) -> MembershipOut:
    employee = await _locked_employee(access, employee_id)
    row = (
        await access.db.execute(
            select(EmployeeMembership).where(
                EmployeeMembership.id == record_id, EmployeeMembership.employee_id == employee.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    await access.audit(
        "employee.membership_changed",
        entity_type="employee",
        entity_id=employee.id,
        after=body.model_dump(mode="json"),
    )
    await access.db.commit()
    return MembershipOut.model_validate(row)


@router.delete("/employees/{employee_id}/memberships/{record_id}", status_code=204)
async def remove_membership(employee_id: uuid.UUID, record_id: uuid.UUID, access: Writes) -> None:
    employee = await _locked_employee(access, employee_id)
    row = (
        await access.db.execute(
            select(EmployeeMembership).where(
                EmployeeMembership.id == record_id, EmployeeMembership.employee_id == employee.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    await access.audit(
        "employee.membership_removed",
        entity_type="employee",
        entity_id=employee.id,
        before={"id": str(row.id)},
    )
    await access.db.delete(row)
    await access.db.commit()
