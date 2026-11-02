"""The company's compliance documents (plan.md 8.15): the 18 a sponsor is expected to hold.

Each type has one current document, with an optional expiry date. Uploading again replaces it: the
old record is archived and its file kept. Reminders about expiry come from the reminders task.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.rbac_matrix import Scope
from app.integrations.storage import PRESIGN_SECONDS
from app.modules.companies.models import Company, ComplianceDocument
from app.modules.companies.reference import COMPLIANCE_DOCUMENT_TYPES, EXPIRING_DAYS
from app.modules.files.models import File
from app.modules.rbac.deps import Access, require

if TYPE_CHECKING:
    from app.modules.files.service import FileService

router = APIRouter(tags=["company"])

Reads = Annotated[Access, Depends(require("company.profile.read"))]
Writes = Annotated[Access, Depends(require("document.file.write"))]
Status = Literal["missing", "current", "expiring", "expired"]
KINDS = frozenset({"pdf", "jpg", "png", "doc", "docx"})


class DocumentRecord(BaseModel):
    id: uuid.UUID
    file_name: str
    expires_on: date | None
    notes: str | None
    uploaded_at: datetime
    status: Status


class DocumentSlot(BaseModel):
    doc_type: str
    label: str
    status: Status
    record: DocumentRecord | None


class ComplianceDocuments(BaseModel):
    slots: list[DocumentSlot]
    filled: int = Field(description="How many of the 18 have a current document.")
    total: int


class DocumentPatch(BaseModel):
    """Only the fields that are sent change."""

    model_config = ConfigDict(extra="forbid")

    expires_on: date | None = None
    notes: Annotated[str, Field(max_length=1000)] | None = None


class DocumentLink(BaseModel):
    url: str
    expires_in: int


def status_of(expires_on: date | None, today: date) -> Status:
    if expires_on is None:
        return "current"
    days = (expires_on - today).days
    if days < 0:
        return "expired"
    return "expiring" if days <= EXPIRING_DAYS else "current"


async def _today(access: Access) -> date:
    zone = (
        await access.db.execute(select(Company.timezone).where(Company.id == access.company_id))
    ).scalar_one_or_none()
    return datetime.now(ZoneInfo(zone or "Europe/London")).date()


def _need_everyone(access: Access) -> None:
    """Writing needs the document permission over the whole company, not just one's own files."""
    if access.scope is not Scope.ALL:
        raise ForbiddenError


async def _current(access: Access, doc_type: str) -> ComplianceDocument | None:
    return (
        await access.db.execute(
            select(ComplianceDocument).where(
                ComplianceDocument.doc_type == doc_type, ComplianceDocument.archived_at.is_(None)
            )
        )
    ).scalar_one_or_none()


async def _by_id(access: Access, document_id: uuid.UUID) -> ComplianceDocument:
    row = (
        await access.db.execute(
            select(ComplianceDocument).where(
                ComplianceDocument.id == document_id, ComplianceDocument.archived_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return row


def _record(row: ComplianceDocument, file_name: str, today: date) -> DocumentRecord:
    return DocumentRecord(
        id=row.id,
        file_name=file_name,
        expires_on=row.expires_on,
        notes=row.notes,
        uploaded_at=row.created_at,
        status=status_of(row.expires_on, today),
    )


@router.get("/compliance-documents", summary="The 18 compliance documents and what is held")
async def list_documents(access: Reads) -> ComplianceDocuments:
    today = await _today(access)
    rows = (
        await access.db.execute(
            select(ComplianceDocument, File.original_name)
            .join(File, File.id == ComplianceDocument.file_id)
            .where(ComplianceDocument.archived_at.is_(None))
        )
    ).all()
    held = {row.doc_type: _record(row, name, today) for row, name in rows}
    slots = [
        DocumentSlot(
            doc_type=doc_type,
            label=label,
            status=held[doc_type].status if doc_type in held else "missing",
            record=held.get(doc_type),
        )
        for doc_type, label in COMPLIANCE_DOCUMENT_TYPES.items()
    ]
    return ComplianceDocuments(slots=slots, filled=len(held), total=len(COMPLIANCE_DOCUMENT_TYPES))


def _files(request: Request) -> FileService:
    service: FileService = request.app.state.files
    return service


@router.post("/compliance-documents", status_code=201, summary="Add or replace a document")
async def add_document(
    request: Request,
    file: UploadFile,
    access: Writes,
    doc_type: Annotated[str, Form(max_length=40)],
    expires_on: Annotated[date | None, Form()] = None,
    notes: Annotated[str | None, Form(max_length=1000)] = None,
) -> DocumentRecord:
    _need_everyone(access)
    if doc_type not in COMPLIANCE_DOCUMENT_TYPES:
        raise AppError(
            "VALIDATION_ERROR",
            "That is not one of the documents we ask for.",
            status_code=422,
            field="doc_type",
        )
    record = await _files(request).upload(
        access,
        file.file,
        filename=file.filename,
        owner_type="company",
        owner_id=access.company_id,
        category="compliance_document",
        kinds=KINDS,
        commit=False,
    )
    replaced = await _current(access, doc_type)
    if replaced is not None:
        replaced.archived_at = datetime.now(UTC)
        await access.db.flush()  # one current document per type: free the slot first
    row = ComplianceDocument(
        company_id=access.company_id,
        doc_type=doc_type,
        file_id=record.id,
        expires_on=expires_on,
        notes=(notes or "").strip() or None,
    )
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "compliance_document.replaced" if replaced else "compliance_document.added",
        entity_type="compliance_document",
        entity_id=row.id,
        summary=COMPLIANCE_DOCUMENT_TYPES[doc_type],
        after={"doc_type": doc_type, "expires_on": expires_on, "file": record.original_name},
    )
    await access.db.commit()
    return _record(row, record.original_name, await _today(access))


@router.patch("/compliance-documents/{document_id}", summary="Change the expiry date or notes")
async def update_document(
    document_id: uuid.UUID, body: DocumentPatch, access: Writes
) -> DocumentRecord:
    _need_everyone(access)
    row = await _by_id(access, document_id)
    before = {"expires_on": row.expires_on, "notes": row.notes}
    changes = body.model_dump(exclude_unset=True)
    if "expires_on" in changes:
        row.expires_on = changes["expires_on"]
    if "notes" in changes:
        row.notes = (changes["notes"] or "").strip() or None
    after = {"expires_on": row.expires_on, "notes": row.notes}
    if before != after:
        await access.audit(
            "compliance_document.updated",
            entity_type="compliance_document",
            entity_id=row.id,
            summary=COMPLIANCE_DOCUMENT_TYPES[row.doc_type],
            before=before,
            after=after,
        )
    await access.db.commit()
    name = (
        await access.db.execute(select(File.original_name).where(File.id == row.file_id))
    ).scalar_one()
    return _record(row, name, await _today(access))


@router.delete("/compliance-documents/{document_id}", status_code=204, summary="Remove a document")
async def remove_document(document_id: uuid.UUID, access: Writes) -> None:
    _need_everyone(access)
    row = await _by_id(access, document_id)
    row.archived_at = datetime.now(UTC)
    await access.audit(
        "compliance_document.removed",
        entity_type="compliance_document",
        entity_id=row.id,
        summary=COMPLIANCE_DOCUMENT_TYPES[row.doc_type],
    )
    await access.db.commit()


@router.get("/compliance-documents/{document_id}/file", summary="A 60-second link to the document")
async def document_link(
    document_id: uuid.UUID,
    request: Request,
    access: Annotated[Access, Depends(require("document.file.read"))],
) -> DocumentLink:
    row = await _by_id(access, document_id)
    url, _ = await _files(request).download_url(access, row.file_id)
    return DocumentLink(url=url, expires_in=PRESIGN_SECONDS)
