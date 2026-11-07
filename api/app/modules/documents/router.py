"""Company document library: scoped metadata, scanned uploads and retained archives."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Annotated, cast
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, Query, Request, Response, UploadFile
from sqlalchemy import func, or_, select

from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.rbac_matrix import Scope
from app.db.ids import uuid7
from app.integrations.storage import PRESIGN_SECONDS
from app.modules.companies.models import Company
from app.modules.documents.models import CompanyDocument
from app.modules.documents.reference import DocumentCategory  # noqa: TC001 -- FastAPI resolves annotations
from app.modules.documents.schemas import CompanyDocumentEdit, CompanyDocumentOut, CompanyDocuments
from app.modules.files.models import File
from app.modules.files.schemas import DownloadOut
from app.modules.rbac.deps import Access, require

if TYPE_CHECKING:
    from app.modules.files.service import FileService

router = APIRouter(prefix="/documents", tags=["documents"])
Reads = Annotated[Access, Depends(require("document.file.read"))]
Writes = Annotated[Access, Depends(require("document.file.write"))]
KINDS = frozenset({"pdf", "jpg", "png", "doc", "docx"})


def _all(access: Access) -> None:
    if access.scope is not Scope.ALL:
        raise ForbiddenError


def _files(request: Request) -> FileService:
    service: FileService = request.app.state.files
    return service


async def _today(access: Access) -> date:
    zone = (
        await access.db.execute(select(Company.timezone).where(Company.id == access.company_id))
    ).scalar_one()
    return datetime.now(ZoneInfo(zone)).date()


def _out(row: CompanyDocument, file: File, today: date) -> CompanyDocumentOut:
    review = row.next_review_date
    status: str = "no_review_date"
    if review is not None:
        status = (
            "overdue"
            if review < today
            else "review_due"
            if review <= today + timedelta(days=30)
            else "current"
        )
    return CompanyDocumentOut(
        id=row.id,
        file_id=file.id,
        title=row.title,
        category=cast("DocumentCategory", row.category),
        next_review_date=review,
        review_status=status,  # type: ignore[arg-type]
        file_name=file.original_name,
        size=file.size,
        scan_status=file.scan_status,  # type: ignore[arg-type]
        uploaded_at=row.created_at,
        archived_at=row.archived_at,
    )


async def _record(
    access: Access, document_id: uuid.UUID, *, lock: bool = False
) -> tuple[CompanyDocument, File]:
    query = (
        select(CompanyDocument, File)
        .join(File, File.id == CompanyDocument.file_id)
        .where(
            CompanyDocument.id == document_id,
            CompanyDocument.company_id == access.company_id,
        )
    )
    if lock:
        query = query.with_for_update(of=CompanyDocument)
    result = (await access.db.execute(query)).one_or_none()
    if result is None:
        raise NotFoundError
    return result[0], result[1]


def _metadata(row: CompanyDocument) -> dict[str, object]:
    return {"title": row.title, "category": row.category, "next_review_date": row.next_review_date}


@router.get("", response_model=CompanyDocuments)
async def list_company_documents(
    access: Reads,
    search: Annotated[str, Query(max_length=200)] = "",
    category: DocumentCategory | None = None,
    show_archived: bool = False,
    review_due: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CompanyDocuments:
    _all(access)
    today = await _today(access)
    query = (
        select(CompanyDocument, File)
        .join(File, File.id == CompanyDocument.file_id)
        .where(CompanyDocument.company_id == access.company_id)
    )
    if not show_archived:
        query = query.where(CompanyDocument.archived_at.is_(None))
    if category:
        query = query.where(CompanyDocument.category == category)
    if search.strip():
        query = query.where(
            or_(
                func.lower(CompanyDocument.title).contains(search.strip().lower(), autoescape=True),
                func.lower(File.original_name).contains(search.strip().lower(), autoescape=True),
            )
        )
    if review_due:
        query = query.where(CompanyDocument.next_review_date <= today + timedelta(days=30))
    total = (
        await access.db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar_one()
    rows = (
        await access.db.execute(
            query.order_by(CompanyDocument.created_at.desc(), CompanyDocument.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return CompanyDocuments(
        items=[_out(row, file, today) for row, file in rows],
        total=total,
        today=today,
        limit=limit,
        offset=offset,
    )


@router.post("", status_code=201, response_model=CompanyDocumentOut)
async def upload_company_document(
    request: Request,
    file: UploadFile,
    access: Writes,
    title: Annotated[str, Form(min_length=1, max_length=200)],
    category: Annotated[DocumentCategory, Form()],
    next_review_date: Annotated[date | None, Form()] = None,
) -> CompanyDocumentOut:
    _all(access)
    title = title.strip()
    if not title:
        raise AppError(
            "VALIDATION_ERROR", "Enter a document title.", status_code=422, field="title"
        )
    document_id = uuid7()
    file_record = await _files(request).upload(
        access,
        file.file,
        filename=file.filename,
        owner_type="company_document",
        owner_id=document_id,
        category=category,
        kinds=KINDS,
        commit=False,
    )
    row = CompanyDocument(
        id=document_id,
        company_id=access.company_id,
        file_id=file_record.id,
        title=title,
        category=category,
        next_review_date=next_review_date,
    )
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "company_document.added",
        entity_type="company_document",
        entity_id=row.id,
        after=_metadata(row),
    )
    await access.db.commit()
    return _out(row, file_record, await _today(access))


@router.get("/{document_id}", response_model=CompanyDocumentOut)
async def get_company_document(document_id: uuid.UUID, access: Reads) -> CompanyDocumentOut:
    _all(access)
    row, file = await _record(access, document_id)
    return _out(row, file, await _today(access))


@router.patch("/{document_id}", response_model=CompanyDocumentOut)
async def edit_company_document(
    document_id: uuid.UUID, body: CompanyDocumentEdit, access: Writes
) -> CompanyDocumentOut:
    _all(access)
    row, file = await _record(access, document_id, lock=True)
    if row.archived_at is not None:
        raise AppError("DOCUMENT_ARCHIVED", "This document is archived.", status_code=409)
    before = _metadata(row)
    row.title = body.title
    row.category = body.category
    row.next_review_date = body.next_review_date
    # Keep the generic file metadata consistent with the library category.
    file.category = body.category
    if before != _metadata(row):
        await access.audit(
            "company_document.updated",
            entity_type="company_document",
            entity_id=row.id,
            before=before,
            after=_metadata(row),
        )
    await access.db.commit()
    return _out(row, file, await _today(access))


@router.delete("/{document_id}", status_code=204)
async def archive_company_document(document_id: uuid.UUID, access: Writes) -> Response:
    _all(access)
    row, _ = await _record(access, document_id, lock=True)
    if row.archived_at is None:
        row.archived_at = datetime.now(UTC)
        await access.audit(
            "company_document.archived",
            entity_type="company_document",
            entity_id=row.id,
            after={"archived_at": row.archived_at},
        )
    await access.db.commit()
    return Response(status_code=204)


@router.get("/{document_id}/download", response_model=DownloadOut)
async def download_company_document(
    document_id: uuid.UUID, request: Request, access: Reads
) -> DownloadOut:
    _all(access)
    row, _ = await _record(access, document_id)
    url, _ = await _files(request).download_url(access, row.file_id)
    return DownloadOut(url=url, expires_in=PRESIGN_SECONDS)
