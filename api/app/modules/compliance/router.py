"""Scoped change logs, official-calendar reporting deadlines and audited reported state."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select

from app.core.errors import ConflictError, NotFoundError
from app.modules.companies.compliance_documents import _today
from app.modules.companies.models import Company, Designation
from app.modules.compliance.calendar import reporting_deadline
from app.modules.compliance.models import ChangeOfCircumstances, OrgChange
from app.modules.compliance.schemas import (
    ArchiveChangeIn,
    ChangeDefaults,
    ChangeIn,
    ChangeOut,
    DeadlineOut,
    FilterState,
    OrgChangeIn,
    OrgChangeOut,
    ReportedIn,
)
from app.modules.compliance.working_days import working_days_between
from app.modules.employees.employment_router import _locked_employee
from app.modules.employees.models import Employee, EmployeeAddress, EmployeeAssignment
from app.modules.employees.router import _employee, _like
from app.modules.identity.models import User
from app.modules.rbac.deps import Access, require
from app.modules.sponsor_documents.models import SponsorDocument
from app.modules.sponsor_documents.router import documents as sponsor_documents

router = APIRouter(tags=["compliance-changes"])
Reads = Annotated[Access, Depends(require("employee.change_of_circumstances.read"))]
Writes = Annotated[Access, Depends(require("employee.change_of_circumstances.write"))]


async def _zone(access: Access) -> ZoneInfo:
    zone = (
        await access.db.execute(select(Company.timezone).where(Company.id == access.company_id))
    ).scalar_one()
    return ZoneInfo(zone)


async def _reporting(access: Access, row: ChangeOfCircumstances | OrgChange) -> dict[str, Any]:
    today = await _today(access)
    zone = await _zone(access)
    reported_date = row.reported_at.astimezone(zone).date() if row.reported_at else None
    status = (
        "reported"
        if reported_date
        else "prompt"
        if row.deadline_date is None
        else "overdue"
        if row.deadline_date < today
        else "unreported"
    )
    reporter = (
        (
            await access.db.execute(
                select(User.first_name, User.last_name).where(User.id == row.reported_by_user_id)
            )
        ).first()
        if row.reported_by_user_id
        else None
    )
    return {
        "id": row.id,
        "change_date": row.change_date,
        "deadline_date": row.deadline_date,
        "calendar_region": row.calendar_region,
        "calendar_checked_at": row.calendar_checked_at,
        "calendar_holidays": row.calendar_holidays,
        "remarks": row.remarks,
        "status": status,
        "working_days_left": working_days_between(
            today,
            row.deadline_date,
            frozenset(date.fromisoformat(d) for d in row.calendar_holidays),
        )
        if not row.reported_at and row.deadline_date and row.deadline_date >= today
        else None,
        "reported_at": row.reported_at,
        "reported_date": reported_date,
        "reported_by_user_id": row.reported_by_user_id,
        "reporter_name": f"{reporter[0]} {reporter[1]}" if reporter else None,
        "reported_reference": row.reported_reference,
        "report_recorded_at": row.report_recorded_at,
        "reported_on_time": reported_date <= row.deadline_date
        if reported_date and row.deadline_date
        else None,
        "created_at": row.created_at,
    }


async def _out(
    access: Access, row: ChangeOfCircumstances, employee: Employee | None = None
) -> ChangeOut:
    employee = employee or await _employee(access, row.employee_id)
    return ChangeOut(
        **await _reporting(access, row),
        change_type=row.change_type,  # type: ignore[arg-type]
        employee_id=row.employee_id,
        employee_name=f"{employee.first_name} {employee.last_name}",
        employee_number=employee.employee_number,
        employment_type=row.employment_type,
        job_title=row.job_title,
        nationality=row.nationality,
        contact_number=row.contact_number,
        address=row.address,
        ack_inform_hr=row.ack_inform_hr,
        ack_home_office_interview=row.ack_home_office_interview,
        documents_snapshot=[uuid.UUID(value) for value in row.documents_snapshot],
    )


async def _org_out(access: Access, row: OrgChange) -> OrgChangeOut:
    return OrgChangeOut(
        **await _reporting(access, row),
        change_type=row.change_type,  # type: ignore[arg-type]
        archived_at=row.archived_at,
        archive_reason=row.archive_reason,
    )


async def _past_event(access: Access, event: date) -> None:
    if event > await _today(access):
        raise ConflictError(
            "The reportable event date cannot be in the future.", field="change_date"
        )


@router.get("/compliance/reporting-deadline", response_model=DeadlineOut)
async def preview_deadline(
    access: Reads, change_date: date, kind: Literal["worker", "organisation", "prompt"] = "worker"
) -> DeadlineOut:
    result = await reporting_deadline(
        access, change_date, None if kind == "prompt" else 20 if kind == "organisation" else 10
    )
    return DeadlineOut(
        deadline_date=result.deadline_date,
        calendar_region=result.region,
        calendar_checked_at=result.checked_at,
        bank_holidays_excluded=list(result.holidays),
    )


@router.get("/employees/{employee_id}/changes/options", response_model=ChangeDefaults)
async def change_defaults(employee_id: uuid.UUID, access: Reads) -> ChangeDefaults:
    employee = await _employee(access, employee_id)
    today = await _today(access)
    role = (
        await access.db.execute(
            select(EmployeeAssignment.employment_type, Designation.title)
            .outerjoin(Designation, Designation.id == EmployeeAssignment.designation_id)
            .where(
                EmployeeAssignment.employee_id == employee_id,
                EmployeeAssignment.effective_from <= today,
                or_(EmployeeAssignment.ended_at.is_(None), EmployeeAssignment.ended_at > today),
            )
            .order_by(EmployeeAssignment.effective_from.desc())
            .limit(1)
        )
    ).first()
    address = (
        await access.db.execute(
            select(EmployeeAddress).where(
                EmployeeAddress.employee_id == employee_id, EmployeeAddress.is_current.is_(True)
            )
        )
    ).scalar_one_or_none()
    address_text = (
        ", ".join(
            value
            for value in (
                address.line1,
                address.line2,
                address.line3,
                address.city_county,
                address.postcode,
                address.country,
            )
            if value
        )
        if address
        else None
    )
    docs = await sponsor_documents(employee_id, access)
    return ChangeDefaults(
        employment_type=role[0] if role else None,  # type: ignore[arg-type]
        job_title=role[1] if role else None,
        nationality=employee.nationality,
        contact_number=employee.phone,
        address=address_text,
        documents=[d for d in docs if not d.superseded_by and not d.withdrawn_at],
    )


@router.get("/employees/{employee_id}/changes", response_model=list[ChangeOut])
async def employee_changes(employee_id: uuid.UUID, access: Reads) -> list[ChangeOut]:
    employee = await _employee(access, employee_id)
    rows = (
        await access.db.execute(
            select(ChangeOfCircumstances)
            .where(ChangeOfCircumstances.employee_id == employee_id)
            .order_by(ChangeOfCircumstances.change_date.desc(), ChangeOfCircumstances.id.desc())
        )
    ).scalars()
    return [await _out(access, row, employee) for row in rows]


@router.post("/employees/{employee_id}/changes", status_code=201, response_model=ChangeOut)
async def add_change(employee_id: uuid.UUID, body: ChangeIn, access: Writes) -> ChangeOut:
    employee = await _locked_employee(access, employee_id)
    await _past_event(access, body.change_date)
    selected = set(body.documents_snapshot)
    if len(selected) != len(body.documents_snapshot):
        raise ConflictError("Choose each document only once.", field="documents_snapshot")
    if selected:
        found = set(
            (
                await access.db.execute(
                    select(SponsorDocument.id).where(
                        SponsorDocument.id.in_(selected),
                        SponsorDocument.employee_id == employee_id,
                        SponsorDocument.superseded_by.is_(None),
                        SponsorDocument.withdrawn_at.is_(None),
                    )
                )
            ).scalars()
        )
        if found != selected:
            raise NotFoundError
    calendar = await reporting_deadline(access, body.change_date, 10)
    data = body.model_dump(exclude={"documents_snapshot"})
    row = ChangeOfCircumstances(
        company_id=access.company_id,
        employee_id=employee_id,
        documents_snapshot=[str(i) for i in body.documents_snapshot],
        **calendar.fields(),
        **data,
    )
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "employee.change_logged",
        entity_type="employee",
        entity_id=employee_id,
        after={
            "change_id": str(row.id),
            "change_type": row.change_type,
            "change_date": str(row.change_date),
            "deadline_date": str(row.deadline_date),
            "document_ids": row.documents_snapshot,
        },
    )
    await access.db.commit()
    return await _out(access, row, employee)


@router.get("/compliance/changes", response_model=list[ChangeOut])
async def changes(
    access: Reads,
    state: FilterState = "all",
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> list[ChangeOut]:
    query = select(ChangeOfCircumstances, Employee).join(
        Employee, Employee.id == ChangeOfCircumstances.employee_id
    )
    if state != "all":
        query = query.where(ChangeOfCircumstances.reported_at.is_(None))
    if state == "overdue":
        query = query.where(ChangeOfCircumstances.deadline_date < await _today(access))
    if q and q.strip():
        for word in q.split():
            pattern = _like(word)
            query = query.where(
                or_(
                    Employee.first_name.ilike(pattern, escape="\\"),
                    Employee.last_name.ilike(pattern, escape="\\"),
                    Employee.employee_number.ilike(pattern, escape="\\"),
                    ChangeOfCircumstances.change_type.ilike(pattern, escape="\\"),
                )
            )
    rows = (
        await access.db.execute(
            query.order_by(
                ChangeOfCircumstances.reported_at.is_not(None),
                ChangeOfCircumstances.deadline_date,
                ChangeOfCircumstances.id.desc(),
            )
        )
    ).all()
    return [await _out(access, row, employee) for row, employee in rows]


async def _mark_reported(
    access: Access, row: ChangeOfCircumstances | OrgChange, body: ReportedIn
) -> None:
    if row.reported_at:
        raise ConflictError("This change is already recorded as reported.")
    if body.reported_date < row.change_date or body.reported_date > await _today(access):
        raise ConflictError(
            "Choose a reporting date from the event date through today.", field="reported_date"
        )
    row.reported_at = datetime.combine(
        body.reported_date, time.min, tzinfo=await _zone(access)
    ).astimezone(UTC)
    row.reported_by_user_id = access.caller.user_id
    row.reported_reference = body.reference
    row.report_recorded_at = datetime.now(UTC)
    employee_change = isinstance(row, ChangeOfCircumstances)
    await access.audit(
        "employee.change_reported" if employee_change else "company.change_reported",
        entity_type="employee" if employee_change else "org_change",
        entity_id=row.employee_id if isinstance(row, ChangeOfCircumstances) else row.id,
        after={
            "change_id": str(row.id),
            "reported_date": str(body.reported_date),
            "reported_by": str(access.caller.user_id),
            "reference": body.reference,
        },
    )
    await access.db.commit()


@router.post("/changes/{change_id}/mark-reported", response_model=ChangeOut)
async def mark_reported(change_id: uuid.UUID, body: ReportedIn, access: Writes) -> ChangeOut:
    row = (
        await access.db.execute(
            select(ChangeOfCircumstances)
            .where(ChangeOfCircumstances.id == change_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    await _employee(access, row.employee_id)
    await _mark_reported(access, row, body)
    return await _out(access, row)


async def _org(access: Access, ident: uuid.UUID, *, lock: bool = False) -> OrgChange:
    query = select(OrgChange).where(OrgChange.id == ident, OrgChange.archived_at.is_(None))
    if lock:
        query = query.with_for_update()
    row = (await access.db.execute(query)).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    if lock and row.reported_at:
        raise ConflictError(
            "Reported organisation changes stay in the audit record and cannot be edited."
        )
    return row


@router.get("/compliance/org-changes", response_model=list[OrgChangeOut])
async def org_changes(access: Reads, state: FilterState = "all") -> list[OrgChangeOut]:
    query = select(OrgChange).where(OrgChange.archived_at.is_(None))
    if state != "all":
        query = query.where(OrgChange.reported_at.is_(None))
    if state == "overdue":
        query = query.where(OrgChange.deadline_date < await _today(access))
    rows = (
        await access.db.execute(
            query.order_by(
                OrgChange.reported_at.is_not(None),
                OrgChange.deadline_date.asc().nullsfirst(),
                OrgChange.id.desc(),
            )
        )
    ).scalars()
    return [await _org_out(access, row) for row in rows]


@router.get("/compliance/org-changes/{change_id}", response_model=OrgChangeOut)
async def org_change(change_id: uuid.UUID, access: Reads) -> OrgChangeOut:
    return await _org_out(access, await _org(access, change_id))


@router.post("/compliance/org-changes", status_code=201, response_model=OrgChangeOut)
async def add_org_change(body: OrgChangeIn, access: Writes) -> OrgChangeOut:
    await _past_event(access, body.change_date)
    calendar = await reporting_deadline(
        access, body.change_date, None if body.change_type == "ao_or_key_contact" else 20
    )
    row = OrgChange(company_id=access.company_id, **body.model_dump(), **calendar.fields())
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "company.change_logged",
        entity_type="org_change",
        entity_id=row.id,
        after={
            "change_type": row.change_type,
            "change_date": str(row.change_date),
            "deadline_date": str(row.deadline_date) if row.deadline_date else None,
        },
    )
    await access.db.commit()
    return await _org_out(access, row)


@router.put("/compliance/org-changes/{change_id}", response_model=OrgChangeOut)
async def update_org_change(
    change_id: uuid.UUID, body: OrgChangeIn, access: Writes
) -> OrgChangeOut:
    row = await _org(access, change_id, lock=True)
    await _past_event(access, body.change_date)
    before = {
        "change_type": row.change_type,
        "change_date": str(row.change_date),
        "deadline_date": str(row.deadline_date) if row.deadline_date else None,
        "remarks": row.remarks,
    }
    calendar = await reporting_deadline(
        access, body.change_date, None if body.change_type == "ao_or_key_contact" else 20
    )
    for key, value in {**body.model_dump(), **calendar.fields()}.items():
        setattr(row, key, value)
    await access.audit(
        "company.change_updated",
        entity_type="org_change",
        entity_id=row.id,
        before=before,
        after={
            "change_type": row.change_type,
            "change_date": str(row.change_date),
            "deadline_date": str(row.deadline_date) if row.deadline_date else None,
            "remarks": row.remarks,
        },
    )
    await access.db.commit()
    return await _org_out(access, row)


@router.delete("/compliance/org-changes/{change_id}", response_model=OrgChangeOut)
async def archive_org_change(
    change_id: uuid.UUID, body: ArchiveChangeIn, access: Writes
) -> OrgChangeOut:
    row = await _org(access, change_id, lock=True)
    row.archived_at = datetime.now(UTC)
    row.archive_reason = body.reason
    await access.audit(
        "company.change_archived", entity_type="org_change", entity_id=row.id, reason=body.reason
    )
    await access.db.commit()
    return await _org_out(access, row)


@router.post("/compliance/org-changes/{change_id}/mark-reported", response_model=OrgChangeOut)
async def mark_org_reported(change_id: uuid.UUID, body: ReportedIn, access: Writes) -> OrgChangeOut:
    row = await _org(access, change_id, lock=True)
    await _mark_reported(access, row, body)
    return await _org_out(access, row)
