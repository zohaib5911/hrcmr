"""Profile photos use the scanned image pipeline and authenticated API delivery (plan 8.3)."""

from __future__ import annotations

import uuid  # noqa: TC003
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, UploadFile
from sqlalchemy import select

from app.core.errors import ForbiddenError, NotFoundError
from app.core.rbac_matrix import Scope
from app.modules.employees.document_router import _files
from app.modules.employees.router import _employee
from app.modules.files.models import File
from app.modules.rbac.deps import Access, require

router = APIRouter(tags=["employees"])
Reads = Annotated[Access, Depends(require("employee.profile.read"))]
Writes = Annotated[Access, Depends(require("employee.profile.write"))]


@router.post("/employees/{employee_id}/photo", status_code=204)
async def upload_photo(
    employee_id: uuid.UUID, request: Request, file: UploadFile, access: Writes
) -> None:
    if access.scope is not Scope.ALL:
        raise ForbiddenError
    employee = await _employee(access, employee_id)
    record = await _files(request).upload(
        access,
        file.file,
        filename=file.filename,
        owner_type="employee",
        owner_id=employee.id,
        category="employee_photo",
        kinds=frozenset({"jpg", "png"}),
        max_bytes=5 * 1024 * 1024,
        commit=False,
    )
    before = employee.photo_file_id
    employee.photo_file_id = record.id
    await access.audit(
        "employee.photo_changed",
        entity_type="employee",
        entity_id=employee.id,
        before={"photo_file_id": str(before) if before else None},
        after={"photo_file_id": str(record.id)},
    )
    await access.db.commit()


@router.get(
    "/employees/{employee_id}/photo",
    response_class=Response,
    responses={
        200: {
            "content": {"image/png": {}, "image/jpeg": {}},
            "description": "Scanned employee photo",
        }
    },
)
async def get_photo(employee_id: uuid.UUID, request: Request, access: Reads) -> Response:
    employee = await _employee(access, employee_id)
    service = _files(request)
    if employee.photo_file_id is None or service.storage is None:
        raise NotFoundError
    record = (
        await access.db.execute(
            select(File).where(
                File.id == employee.photo_file_id,
                File.owner_type == "employee",
                File.owner_id == employee.id,
                File.scan_status == "clean",
            )
        )
    ).scalar_one_or_none()
    if record is None or record.mime not in {"image/jpeg", "image/png"}:
        raise NotFoundError
    body = await service.storage.read(record.storage_key)
    return Response(
        body,
        media_type=record.mime,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )
