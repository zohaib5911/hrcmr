"""Uploading and downloading files (plan.md 4.5): ``POST /files`` and the 60-second links."""

from __future__ import annotations

import uuid  # noqa: TC003
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Form, Request, UploadFile

from app.integrations.storage import PRESIGN_SECONDS
from app.modules.files.schemas import DownloadOut, FileOut
from app.modules.rbac.deps import Access, require

if TYPE_CHECKING:
    from app.modules.files.models import File
    from app.modules.files.service import FileService

router = APIRouter(tags=["files"])


def _service(request: Request) -> FileService:
    service: FileService = request.app.state.files
    return service


def _out(record: File) -> FileOut:
    return FileOut(
        id=record.id,
        original_name=record.original_name,
        mime=record.mime,
        size=record.size,
        sha256=record.sha256,
        scan_status=record.scan_status,  # type: ignore[arg-type]
        category=record.category,
        owner_type=record.owner_type,
        owner_id=record.owner_id,
        created_at=record.created_at,
    )


@router.post("/files", status_code=201, summary="Upload a file")
async def upload_file(
    request: Request,
    file: UploadFile,
    access: Annotated[Access, Depends(require("document.file.write"))],
    owner_type: Annotated[str | None, Form(max_length=40)] = None,
    owner_id: Annotated[uuid.UUID | None, Form()] = None,
    category: Annotated[str | None, Form(max_length=40)] = None,
) -> FileOut:
    record = await _service(request).upload(
        access,
        file.file,
        filename=file.filename,
        owner_type=owner_type or None,
        owner_id=owner_id,
        category=category or None,
    )
    return _out(record)


@router.get("/files/{file_id}", summary="What we hold about a file")
async def get_file(
    file_id: uuid.UUID,
    request: Request,
    access: Annotated[Access, Depends(require("document.file.read"))],
) -> FileOut:
    return _out(await _service(request).get(access, file_id))


@router.get("/files/{file_id}/download", summary="A 60-second download link")
async def download_file(
    file_id: uuid.UUID,
    request: Request,
    access: Annotated[Access, Depends(require("document.file.read"))],
) -> DownloadOut:
    url, _ = await _service(request).download_url(access, file_id)
    return DownloadOut(url=url, expires_in=PRESIGN_SECONDS)
