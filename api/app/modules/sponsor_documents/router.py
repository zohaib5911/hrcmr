"""Sponsor evidence: explicit versions, reasoned withdrawal and audited renewal planning."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

from app.core.crypto import mask_tail
from app.core.errors import ConflictError, NotFoundError
from app.core.rbac_matrix import scope_for
from app.db.ids import uuid7
from app.db.rtw import employee_rtw_status
from app.integrations.storage import PRESIGN_SECONDS
from app.modules.companies.compliance_documents import _today
from app.modules.employees.document_router import _files
from app.modules.employees.employment_router import _locked_employee
from app.modules.employees.models import Employee
from app.modules.employees.router import _employee
from app.modules.files.models import File
from app.modules.files.schemas import DownloadOut
from app.modules.rbac.deps import Access, require
from app.modules.sponsor_documents.models import SponsorDocument
from app.modules.sponsor_documents.reference import SPONSORED_ROUTES
from app.modules.sponsor_documents.schemas import (
    DocumentStatus,
    RenewalIn,
    SponsorDocumentIn,
    SponsorDocumentOut,
    SponsoredEmployee,
    SponsoredEmployees,
    WithdrawalIn,
)

router = APIRouter(tags=["sponsor-documents"])
# Sponsor compliance metadata follows the RTW permissions, including own-read. File-own writes
# alone do not allow an employee to edit their compliance record.
Reads = Annotated[Access, Depends(require("employee.rtw.read"))]
Writes = Annotated[Access, Depends(require("employee.rtw.write"))]
Overview = Annotated[Access, Depends(require("compliance.overview.read"))]


def current() -> Any:
    return SponsorDocument.superseded_by.is_(None) & SponsorDocument.withdrawn_at.is_(None)


def status_of(row: SponsorDocument, today: date, clean: bool) -> DocumentStatus:
    if row.withdrawn_at:
        return "withdrawn"
    if row.superseded_by:
        return "superseded"
    if row.expiry_date and row.expiry_date < today:
        return "expired"
    if not clean:
        return "evidence_missing"
    if row.expiry_date and (row.expiry_date - today).days <= 90:
        return "expiring"
    return "current"


async def _out(access: Access, row: SponsorDocument) -> SponsorDocumentOut:
    file = (
        (
            await access.db.execute(
                select(File).where(
                    File.id == row.evidence_file_id,
                    File.owner_type == "employee",
                    File.owner_id == row.employee_id,
                )
            )
        ).scalar_one_or_none()
        if row.evidence_file_id
        else None
    )
    return SponsorDocumentOut(
        id=row.id,
        doc_type=row.doc_type,  # type: ignore[arg-type]
        reference_number_masked=mask_tail(row.reference_number, 3)
        if row.reference_number
        else None,
        issuing_country=row.issuing_country,
        visa_route=row.visa_route,  # type: ignore[arg-type]
        cos_number_masked=mask_tail(row.cos_number, 3) if row.cos_number else None,
        soc_code=row.soc_code,
        sponsored_salary=row.sponsored_salary
        if scope_for(access.role, "employee.compensation.read") is not None
        else None,
        issue_date=row.issue_date,
        expiry_date=row.expiry_date,
        review_date=row.review_date,
        evidence_file_id=row.evidence_file_id,
        evidence_file_name=file.original_name if file else None,
        evidence_scan_status=file.scan_status if file else None,
        remarks=row.remarks,
        version=row.version,
        superseded_by=row.superseded_by,
        withdrawn_at=row.withdrawn_at,
        withdraw_reason=row.withdraw_reason,
        renewal_date=row.renewal_date,
        renewal_notes=row.renewal_notes,
        created_at=row.created_at,
        status=status_of(
            row, await _today(access), file is not None and file.scan_status == "clean"
        ),
    )


async def _by_id(access: Access, document_id: uuid.UUID, *, lock: bool = False) -> SponsorDocument:
    row = (
        await access.db.execute(select(SponsorDocument).where(SponsorDocument.id == document_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    if lock:
        await _locked_employee(access, row.employee_id)
        await access.db.refresh(row)
        if row.superseded_by or row.withdrawn_at:
            raise ConflictError("This version is no longer current. Open the current document.")
    else:
        await _employee(access, row.employee_id)
    return row


async def _evidence(access: Access, employee_id: uuid.UUID, file_id: uuid.UUID | None) -> None:
    if (
        file_id
        and not (
            await access.db.execute(
                select(File.id).where(
                    File.id == file_id,
                    File.owner_type == "employee",
                    File.owner_id == employee_id,
                    File.scan_status == "clean",
                )
            )
        ).first()
    ):
        raise NotFoundError


@router.get("/employees/{employee_id}/sponsor-documents", response_model=list[SponsorDocumentOut])
async def documents(employee_id: uuid.UUID, access: Reads) -> list[SponsorDocumentOut]:
    await _employee(access, employee_id)
    rows = (
        await access.db.execute(
            select(SponsorDocument)
            .where(SponsorDocument.employee_id == employee_id)
            .order_by(SponsorDocument.doc_type, SponsorDocument.version.desc())
        )
    ).scalars()
    return [await _out(access, row) for row in rows]


async def _record(
    access: Access,
    employee_id: uuid.UUID,
    body: SponsorDocumentIn,
    source: SponsorDocument | None = None,
) -> SponsorDocumentOut:
    await _evidence(access, employee_id, body.evidence_file_id)
    data = body.model_dump()
    if source:
        if body.doc_type != source.doc_type:
            raise ConflictError("A new version must keep the same document type.", field="doc_type")
        # Inputs never reveal stored references; blank fields preserve them on a new version.
        for key in ("reference_number", "cos_number"):
            if data[key] is None:
                data[key] = getattr(source, key)
    elif (
        await access.db.execute(
            select(SponsorDocument.id).where(
                SponsorDocument.employee_id == employee_id,
                SponsorDocument.doc_type == body.doc_type,
                current(),
            )
        )
    ).first():
        raise ConflictError("A current document already exists. Update it to record a new version.")
    version = (
        await access.db.execute(
            select(func.coalesce(func.max(SponsorDocument.version), 0)).where(
                SponsorDocument.employee_id == employee_id,
                SponsorDocument.doc_type == body.doc_type,
            )
        )
    ).scalar_one() + 1
    ident = uuid7()
    if source:
        source.superseded_by = ident
        await access.db.flush()
    row = SponsorDocument(
        id=ident, company_id=access.company_id, employee_id=employee_id, version=version, **data
    )
    access.db.add(row)
    await access.db.flush()
    from app.modules.compliance.reminder_service import synchronize_employee

    await synchronize_employee(
        access.db, employee_id, access.audit_context, today=await _today(access)
    )
    await access.audit(
        "employee.sponsor_document_versioned" if source else "employee.sponsor_document_added",
        entity_type="employee",
        entity_id=employee_id,
        after={
            "document_id": str(row.id),
            "doc_type": row.doc_type,
            "version": row.version,
            "previous_id": str(source.id) if source else None,
        },
    )
    await access.db.commit()
    return await _out(access, row)


@router.post(
    "/employees/{employee_id}/sponsor-documents", status_code=201, response_model=SponsorDocumentOut
)
async def add_document(
    employee_id: uuid.UUID, body: SponsorDocumentIn, access: Writes
) -> SponsorDocumentOut:
    await _locked_employee(access, employee_id)
    return await _record(access, employee_id, body)


@router.post(
    "/sponsor-documents/{document_id}/versions", status_code=201, response_model=SponsorDocumentOut
)
async def update_document(
    document_id: uuid.UUID, body: SponsorDocumentIn, access: Writes
) -> SponsorDocumentOut:
    source = await _by_id(access, document_id, lock=True)
    return await _record(access, source.employee_id, body, source)


@router.post("/sponsor-documents/{document_id}/withdraw", response_model=SponsorDocumentOut)
async def withdraw_document(
    document_id: uuid.UUID, body: WithdrawalIn, access: Writes
) -> SponsorDocumentOut:
    row = await _by_id(access, document_id, lock=True)
    row.withdrawn_at = datetime.now(UTC)
    row.withdraw_reason = body.reason
    await access.db.flush()
    from app.modules.compliance.reminder_service import synchronize_employee

    await synchronize_employee(
        access.db, row.employee_id, access.audit_context, today=await _today(access)
    )
    await access.audit(
        "employee.sponsor_document_withdrawn",
        entity_type="employee",
        entity_id=row.employee_id,
        after={"document_id": str(row.id), "doc_type": row.doc_type, "version": row.version},
        reason=body.reason,
    )
    await access.db.commit()
    return await _out(access, row)


@router.post("/sponsor-documents/{document_id}/renewal", response_model=SponsorDocumentOut)
async def plan_renewal(
    document_id: uuid.UUID, body: RenewalIn, access: Writes
) -> SponsorDocumentOut:
    row = await _by_id(access, document_id, lock=True)
    if body.renewal_date < await _today(access):
        raise ConflictError(
            "Choose a renewal target date from today onwards.", field="renewal_date"
        )
    previous = {
        "renewal_date": str(row.renewal_date) if row.renewal_date else None,
        "notes": row.renewal_notes,
    }
    row.renewal_date = body.renewal_date
    row.renewal_notes = body.notes
    await access.audit(
        "employee.sponsor_document_renewal_planned",
        entity_type="employee",
        entity_id=row.employee_id,
        before=previous,
        after={
            "document_id": str(row.id),
            "renewal_date": str(body.renewal_date),
            "notes": body.notes,
        },
    )
    await access.db.commit()
    return await _out(access, row)


@router.get("/sponsor-documents/{document_id}/evidence", response_model=DownloadOut)
async def evidence(document_id: uuid.UUID, request: Request, access: Reads) -> DownloadOut:
    row = await _by_id(access, document_id)
    if row.evidence_file_id is None:
        raise NotFoundError
    file = await _files(request).get(access, row.evidence_file_id)
    if file.owner_type != "employee" or file.owner_id != row.employee_id:
        raise NotFoundError
    url, _ = await _files(request).download_url(access, file.id)
    return DownloadOut(url=url, expires_in=PRESIGN_SECONDS)


@router.get("/compliance/sponsored-employees", response_model=SponsoredEmployees)
async def sponsored_employees(access: Overview) -> SponsoredEmployees:
    rows = (
        await access.db.execute(
            select(Employee, SponsorDocument, employee_rtw_status.c.status)
            .join(SponsorDocument, SponsorDocument.employee_id == Employee.id)
            .join(employee_rtw_status, employee_rtw_status.c.employee_id == Employee.id)
            .where(
                current(),
                SponsorDocument.doc_type == "visa",
                SponsorDocument.visa_route.in_(SPONSORED_ROUTES),
                Employee.status != "archived",
                employee_rtw_status.c.company_id == access.company_id,
            )
            .order_by(func.lower(Employee.last_name), func.lower(Employee.first_name))
        )
    ).all()
    return SponsoredEmployees(
        employees=[
            SponsoredEmployee(
                id=e.id,
                employee_number=e.employee_number,
                first_name=e.first_name,
                last_name=e.last_name,
                visa_route=d.visa_route,
                cos_number_masked=mask_tail(d.cos_number, 3) if d.cos_number else None,
                soc_code=d.soc_code,
                expiry_date=d.expiry_date,
                rtw_status=status,
            )
            for e, d, status in rows
        ]
    )
