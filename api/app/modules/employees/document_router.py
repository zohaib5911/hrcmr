"""Employee documents use the same scanned upload and short-lived downloads as company files."""

from __future__ import annotations

import uuid  # noqa: TC003
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Form, Request, UploadFile
from sqlalchemy import select

from app.core.errors import NotFoundError
from app.integrations.storage import PRESIGN_SECONDS
from app.modules.employees.document_schemas import DocumentCategory, EmployeeDocumentOut
from app.modules.employees.models import EmployeeDocument
from app.modules.employees.router import _employee as reachable_employee
from app.modules.files.models import File
from app.modules.files.schemas import DownloadOut
from app.modules.rbac.deps import Access, require

if TYPE_CHECKING:
    from app.modules.files.service import FileService

router = APIRouter(tags=["employees"])
Reads = Annotated[Access, Depends(require("document.file.read"))]
Writes = Annotated[Access, Depends(require("document.file.write"))]


def _files(request: Request) -> FileService:
    service: FileService = request.app.state.files
    return service


def _out(row: EmployeeDocument, file: File) -> EmployeeDocumentOut:
    return EmployeeDocumentOut(
        id=row.id,
        file_id=file.id,
        file_name=file.original_name,
        category=row.category,  # type: ignore[arg-type]
        notes=row.notes,
        size=file.size,
        scan_status=file.scan_status,  # type: ignore[arg-type]
        uploaded_at=row.created_at,
    )


@router.get("/employees/{employee_id}/documents", response_model=list[EmployeeDocumentOut])
async def list_documents(employee_id: uuid.UUID, access: Reads) -> list[EmployeeDocumentOut]:
    await reachable_employee(access, employee_id)
    rows = (
        await access.db.execute(
            select(EmployeeDocument, File)
            .join(File, File.id == EmployeeDocument.file_id)
            .where(EmployeeDocument.employee_id == employee_id)
            .order_by(EmployeeDocument.created_at.desc(), EmployeeDocument.id.desc())
        )
    ).all()
    return [_out(row, file) for row, file in rows]


@router.post(
    "/employees/{employee_id}/documents", status_code=201, response_model=EmployeeDocumentOut
)
async def upload_document(
    employee_id: uuid.UUID,
    request: Request,
    file: UploadFile,
    category: Annotated[DocumentCategory, Form()],
    access: Writes,
    notes: Annotated[str | None, Form(max_length=1000)] = None,
) -> EmployeeDocumentOut:
    employee = await reachable_employee(access, employee_id)
    record = await _files(request).upload(
        access,
        file.file,
        filename=file.filename,
        owner_type="employee",
        owner_id=employee.id,
        category=category,
        commit=False,
    )
    row = EmployeeDocument(
        company_id=access.company_id,
        employee_id=employee.id,
        file_id=record.id,
        category=category,
        notes=(notes or "").strip() or None,
    )
    access.db.add(row)
    await access.db.flush()
    await access.audit(
        "employee.document_added",
        entity_type="employee",
        entity_id=employee.id,
        after={"document_id": str(row.id), "category": category, "file_name": record.original_name},
    )
    await access.db.commit()
    return _out(row, record)


@router.get("/employees/{employee_id}/documents/{document_id}/download", response_model=DownloadOut)
async def download_document(
    employee_id: uuid.UUID, document_id: uuid.UUID, request: Request, access: Reads
) -> DownloadOut:
    await reachable_employee(access, employee_id)
    row = (
        await access.db.execute(
            select(EmployeeDocument).where(
                EmployeeDocument.id == document_id, EmployeeDocument.employee_id == employee_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    url, _ = await _files(request).download_url(access, row.file_id)
    return DownloadOut(url=url, expires_in=PRESIGN_SECONDS)
