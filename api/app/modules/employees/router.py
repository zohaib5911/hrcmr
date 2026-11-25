"""Employees (plan.md 8.3): the list and its summary. The record itself, creating one and the
profile come in T6.2 and T6.3. A person sees what their permission reaches: everyone, their reports,
or only themselves."""

from __future__ import annotations

import uuid  # noqa: TC003  (FastAPI reads the annotations at run time)
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, UploadFile
from sqlalchemy import delete, func, or_, select

from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.rbac_matrix import Scope
from app.db.rtw import employee_rtw_status
from app.modules.audit.models import AuditEvent
from app.modules.companies.models import Department, Designation
from app.modules.compliance.models import ChangeOfCircumstances
from app.modules.employees.models import (
    Employee,
    EmployeeAssignment,
    EmployeeCompensation,
    EmployeeDocument,
    current_assignment,
)
from app.modules.employees.schemas import (
    EmployeeIn,
    EmployeeList,
    EmployeeProfile,
    EmployeeRow,
    EmployeeSummary,
    OptOutChange,
    PermanentDelete,
    Status,
    StatusChange,
)
from app.modules.employees.service import add_employee, number_key
from app.modules.policies import service as policy_service
from app.modules.policies.models import PolicyAcceptance
from app.modules.rbac.deps import Access, require
from app.modules.rtw.models import RTWCheck
from app.modules.rtw.schemas import FILTER_STATUSES, RTWFilter
from app.modules.sponsor_documents.models import SponsorDocument

router = APIRouter(tags=["employees"])

Reads = Annotated[Access, Depends(require("employee.profile.read"))]
Writes = Annotated[Access, Depends(require("employee.profile.write"))]
Deletes = Annotated[Access, Depends(require("employee.profile.delete"))]
AGREEMENT_NOTE = "48-hour week opt-out agreement"
LIMIT = 2000  # rows per page; follow next_offset for the rest (nobody is ever cut off)


def _require_full_write(access: Access) -> None:
    # Own profile writes cover contact details, not HR lifecycle/create/agreement operations.
    if access.scope is not Scope.ALL:
        raise ForbiddenError


async def _reachable(access: Access) -> frozenset[uuid.UUID] | None:
    """The employees this person may see: None means everyone."""
    if access.scope is Scope.ALL:
        return None
    mine = {access.employee_id} if access.employee_id else set()
    if access.scope is Scope.REPORTS and access.employee_id:
        mine |= await access.reports.reports_of(access.employee_id)
    return frozenset(mine)


def _like(text_: str) -> str:
    escaped = text_.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@router.get("/employees", response_model=EmployeeList)
async def list_employees(
    access: Reads,
    status: Annotated[Status | None, Query()] = None,
    department_id: Annotated[uuid.UUID | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100, description="Name or number contains.")] = None,
    rtw: Annotated[RTWFilter | None, Query()] = None,
    archived: Annotated[
        bool, Query(description="Include archived records (or, with status=archived, only them).")
    ] = False,
    offset: Annotated[int, Query(ge=0, description="Rows to skip (from next_offset).")] = 0,
) -> EmployeeList:
    reach = await _reachable(access)
    today = await access.reports.today()
    query = (
        select(
            Employee,
            EmployeeAssignment.department_id,
            Department.name,
            Designation.title,
            employee_rtw_status.c.status,
        )
        .outerjoin(
            EmployeeAssignment,
            (EmployeeAssignment.employee_id == Employee.id) & current_assignment(today),
        )
        .outerjoin(Department, Department.id == EmployeeAssignment.department_id)
        .outerjoin(Designation, Designation.id == EmployeeAssignment.designation_id)
        .join(
            employee_rtw_status,
            (employee_rtw_status.c.employee_id == Employee.id)
            & (employee_rtw_status.c.company_id == access.company_id),
        )
    )
    if reach is not None:
        query = query.where(Employee.id.in_(reach))
    if status:
        query = query.where(Employee.status == status)
    elif not archived:
        query = query.where(Employee.status != "archived")
    if department_id:
        query = query.where(EmployeeAssignment.department_id == department_id)
    if rtw:
        query = query.where(employee_rtw_status.c.status.in_(FILTER_STATUSES[rtw]))
    if q and q.strip():
        pattern = _like(q.strip())
        query = query.where(
            or_(
                Employee.employee_number.ilike(pattern, escape="\\"),
                func.regexp_replace(Employee.employee_number, r"\s", "", "g").ilike(
                    _like("".join(q.split())), escape="\\"
                ),
                Employee.first_name.ilike(pattern, escape="\\"),
                Employee.last_name.ilike(pattern, escape="\\"),
                func.concat(Employee.first_name, " ", Employee.last_name).ilike(
                    pattern, escape="\\"
                ),
            )
        )
    total = (
        await access.db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar_one()
    rows = (
        await access.db.execute(
            query.order_by(
                func.lower(Employee.last_name), func.lower(Employee.first_name), Employee.id
            )
            .offset(offset)
            .limit(LIMIT)
        )
    ).all()
    return EmployeeList(
        employees=[
            EmployeeRow(
                id=e.id,
                employee_number=e.employee_number,
                first_name=e.first_name,
                last_name=e.last_name,
                email=e.email,
                status=e.status,
                hire_date=e.hire_date,
                department_id=department_id_,
                department=department,
                designation=designation,
                has_photo=e.photo_file_id is not None,
                rtw_status=rtw_status_,
            )
            for e, department_id_, department, designation, rtw_status_ in rows
        ],
        total=total,
        next_offset=offset + len(rows) if rows and offset + len(rows) < total else None,
    )


@router.get("/employees/summary", response_model=EmployeeSummary)
async def employee_summary(access: Reads) -> EmployeeSummary:
    reach = await _reachable(access)
    query = select(Employee.status, func.count()).group_by(Employee.status)
    if reach is not None:
        query = query.where(Employee.id.in_(reach))
    counts = dict((await access.db.execute(query)).all())
    live = sum(n for status, n in counts.items() if status != "archived")
    rtw_query = (
        select(employee_rtw_status.c.status, func.count())
        .join(Employee, Employee.id == employee_rtw_status.c.employee_id)
        .where(employee_rtw_status.c.company_id == access.company_id, Employee.status != "archived")
        .group_by(employee_rtw_status.c.status)
    )
    if reach is not None:
        rtw_query = rtw_query.where(Employee.id.in_(reach))
    rtw_counts: dict[str, int] = dict((await access.db.execute(rtw_query)).all())
    return EmployeeSummary(
        total=live,
        active=counts.get("active", 0),
        on_leave=counts.get("on_leave", 0),
        leavers=counts.get("leaver", 0),
        archived=counts.get("archived", 0),
        rtw_verified=rtw_counts.get("verified", 0),
        rtw_needs_attention=live - rtw_counts.get("verified", 0),
    )


def _row(e: Employee) -> EmployeeRow:
    return EmployeeRow(
        id=e.id,
        employee_number=e.employee_number,
        first_name=e.first_name,
        last_name=e.last_name,
        email=e.email,
        status=e.status,  # type: ignore[arg-type]
        hire_date=e.hire_date,
        department_id=None,
        department=None,
        designation=None,
        has_photo=False,
    )


def _number_key(number: str) -> str:
    return number_key(number)


@router.post("/employees", status_code=201, response_model=EmployeeRow)
async def create_employee(body: EmployeeIn, request: Request, access: Writes) -> EmployeeRow:
    """A new record with the essentials. The number must be unique in the company, ignoring case
    and spaces ("E 001" and "e001" are the same)."""
    _require_full_write(access)
    employee = await add_employee(access.db, access.company_id, body)
    await access.audit(
        "employee.created",
        entity_type="employee",
        entity_id=employee.id,
        after={
            "employee_number": employee.employee_number,
            "name": f"{employee.first_name} {employee.last_name}",
            "hire_date": employee.hire_date.isoformat(),
            "status": employee.status,
        },
    )
    # New starters join sent policies marked "send to new starters", in this same transaction.
    await policy_service.assign_new_starters(
        access.db,
        access.audit_context,
        await policy_service.company_day(access.db),
        request.app.state.settings.web_origin,
        only=[employee.id],
    )
    await access.db.commit()
    return _row(employee)


async def _employee(access: Access, employee_id: uuid.UUID) -> Employee:
    """The record, if this person may reach it; otherwise a 404 (existence is not revealed)."""
    employee = (
        await access.db.execute(select(Employee).where(Employee.id == employee_id))
    ).scalar_one_or_none()
    if employee is None or not await access.can_reach(employee_id):
        raise NotFoundError
    return employee


async def _agreement_on_file(access: Access, employee_id: uuid.UUID) -> bool:
    return (
        await access.db.execute(
            select(EmployeeDocument.id).where(
                EmployeeDocument.employee_id == employee_id,
                EmployeeDocument.notes == AGREEMENT_NOTE,
            )
        )
    ).first() is not None


async def _delete_blocker(access: Access, employee_id: uuid.UUID) -> str | None:
    """Why this record may not be deleted for good, or None. A record with history is archived."""
    history = {
        "policy sign-offs or assignments": select(PolicyAcceptance.id).where(
            PolicyAcceptance.employee_id == employee_id
        ),
        "change-of-circumstances records": select(ChangeOfCircumstances.id).where(
            ChangeOfCircumstances.employee_id == employee_id
        ),
        "sponsor documents": select(SponsorDocument.id).where(
            SponsorDocument.employee_id == employee_id
        ),
        "Right to Work checks": select(RTWCheck.id).where(
            RTWCheck.subject_type == "employee", RTWCheck.subject_id == employee_id
        ),
        "a role": select(EmployeeAssignment.id).where(
            EmployeeAssignment.employee_id == employee_id
        ),
        "a salary record": select(EmployeeCompensation.id).where(
            EmployeeCompensation.employee_id == employee_id
        ),
        "a document": select(EmployeeDocument.id).where(
            EmployeeDocument.employee_id == employee_id
        ),
        "recorded changes": select(AuditEvent.id).where(
            AuditEvent.entity_type == "employee",
            AuditEvent.entity_id == employee_id,
            AuditEvent.action != "employee.created",
        ),
    }
    for what, query in history.items():
        if (await access.db.execute(query.limit(1))).first() is not None:
            return f"This record has {what}. Archive it instead, so that history is kept."
    return None


async def _profile(access: Access, employee: Employee) -> EmployeeProfile:
    role = (
        await access.db.execute(
            select(Department.name, Designation.title, EmployeeAssignment.employment_type)
            .select_from(EmployeeAssignment)
            .outerjoin(Department, Department.id == EmployeeAssignment.department_id)
            .outerjoin(Designation, Designation.id == EmployeeAssignment.designation_id)
            .where(
                EmployeeAssignment.employee_id == employee.id,
                current_assignment(await access.reports.today()),
            )
        )
    ).first()
    documents = (
        await access.db.execute(
            select(func.count())
            .select_from(EmployeeDocument)
            .where(EmployeeDocument.employee_id == employee.id)
        )
    ).scalar_one()
    blocker = await _delete_blocker(access, employee.id)
    rtw = (
        await access.db.execute(
            select(employee_rtw_status.c.status, employee_rtw_status.c.follow_up_due_on).where(
                employee_rtw_status.c.employee_id == employee.id,
                employee_rtw_status.c.company_id == access.company_id,
            )
        )
    ).one()
    return EmployeeProfile(
        id=employee.id,
        employee_number=employee.employee_number,
        first_name=employee.first_name,
        last_name=employee.last_name,
        email=employee.email,
        phone=employee.phone,
        status=employee.status,  # type: ignore[arg-type]
        hire_date=employee.hire_date,
        leave_date=employee.leave_date,
        department=role[0] if role else None,
        designation=role[1] if role else None,
        employment_type=role[2] if role else None,
        has_photo=employee.photo_file_id is not None,
        rtw_status=rtw[0],
        rtw_follow_up_due_on=rtw[1],
        opted_out_48h_week=employee.opted_out_48h_week,
        has_opt_out_agreement=await _agreement_on_file(access, employee.id),
        documents=documents,
        can_delete=blocker is None,
        delete_blocker=blocker,
    )


@router.get("/employees/{employee_id}", response_model=EmployeeProfile)
async def get_employee(employee_id: uuid.UUID, access: Reads) -> EmployeeProfile:
    return await _profile(access, await _employee(access, employee_id))


@router.post("/employees/{employee_id}/status", response_model=EmployeeProfile)
async def change_status(
    employee_id: uuid.UUID, body: StatusChange, access: Writes
) -> EmployeeProfile:
    """Set to active, on leave, leaver or archived. A leaving date is optional."""
    _require_full_write(access)
    employee = await _employee(access, employee_id)
    before = {"status": employee.status, "leave_date": employee.leave_date}
    employee.status = body.status
    employee.leave_date = body.leave_date if body.status in ("leaver", "on_leave") else None
    after = {"status": employee.status, "leave_date": employee.leave_date}
    if before != after:
        from app.modules.companies.compliance_documents import _today
        from app.modules.compliance.reminder_service import synchronize_employee

        await synchronize_employee(
            access.db, employee.id, access.audit_context, today=await _today(access)
        )
        await access.audit(
            "employee.status_changed",
            entity_type="employee",
            entity_id=employee.id,
            before={k: str(v) if v else None for k, v in before.items()},
            after={k: str(v) if v else None for k, v in after.items()},
        )
    await access.db.commit()
    return await _profile(access, employee)


@router.put("/employees/{employee_id}/opt-out-48h", response_model=EmployeeProfile)
async def set_opt_out(
    employee_id: uuid.UUID, body: OptOutChange, access: Writes
) -> EmployeeProfile:
    """Record an opt-out of the 48-hour week. The signed agreement must be filed first."""
    _require_full_write(access)
    employee = await _employee(access, employee_id)
    if body.opted_out and not await _agreement_on_file(access, employee.id):
        raise ConflictError("Upload the signed opt-out agreement first.", field="opted_out")
    if employee.opted_out_48h_week != body.opted_out:
        employee.opted_out_48h_week = body.opted_out
        await access.audit(
            "employee.opt_out_48h_changed",
            entity_type="employee",
            entity_id=employee.id,
            after={"opted_out": body.opted_out},
        )
    await access.db.commit()
    return await _profile(access, employee)


@router.post("/employees/{employee_id}/opt-out-48h/agreement", status_code=204)
async def upload_agreement(
    employee_id: uuid.UUID, request: Request, file: UploadFile, access: Writes
) -> None:
    _require_full_write(access)
    employee = await _employee(access, employee_id)
    record = await request.app.state.files.upload(
        access,
        file.file,
        filename=file.filename,
        owner_type="employee",
        owner_id=employee.id,
        category="hr_record",
        commit=False,
    )
    access.db.add(
        EmployeeDocument(
            company_id=access.company_id,
            employee_id=employee.id,
            file_id=record.id,
            category="hr_record",
            notes=AGREEMENT_NOTE,
        )
    )
    await access.audit(
        "employee.opt_out_agreement_added",
        entity_type="employee",
        entity_id=employee.id,
        after={"file": record.original_name},
    )
    await access.db.commit()


@router.delete("/employees/{employee_id}", status_code=204)
async def delete_employee(employee_id: uuid.UUID, body: PermanentDelete, access: Deletes) -> None:
    """Delete a record made by mistake: one with no history, and only when the full name
    is typed; anything else is archived."""
    employee = await _employee(access, employee_id)
    if body.confirm_name.strip().lower() != f"{employee.first_name} {employee.last_name}".lower():
        raise AppError(
            "VALIDATION_ERROR",
            "Type the person's full name exactly to confirm.",
            status_code=422,
            field="confirm_name",
        )
    blocker = await _delete_blocker(access, employee.id)
    if blocker:
        raise ConflictError(blocker)
    await access.audit(
        "employee.deleted",
        entity_type="employee",
        entity_id=employee.id,
        summary=f"{employee.employee_number}: {employee.first_name} {employee.last_name}",
    )
    await access.db.execute(delete(Employee).where(Employee.id == employee.id))
    await access.db.commit()
