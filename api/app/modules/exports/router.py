"""A company's data export (plan 8.16, API item 22, T16.4): ask (with step-up), follow, download.

Only the requester can see or download their export, and a download always needs their signed-in
session: the e-mail link is an API address that asks for it, not a bearer link.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, datetime
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.errors import AppError, NotFoundError
from app.core.logging import get_logger
from app.jobs.exports import queue_id
from app.jobs.queue import open_queue
from app.modules.auth.sessions import require_step_up
from app.modules.exports.models import DataExport
from app.modules.files.models import File
from app.modules.rbac.deps import Access, require

router = APIRouter(prefix="/companies/me", tags=["account-lifecycle"])
Exporter = Annotated[Access, Depends(require("company.export"))]
logger = get_logger("app.exports")

ExportStatus = Literal["queued", "ready", "failed", "expired"]


class ExportOut(BaseModel):
    id: uuid.UUID
    status: ExportStatus
    created_at: datetime
    finished_at: datetime | None
    expires_at: datetime | None
    error_code: str | None


def _expired(row: DataExport, now: datetime) -> bool:
    return row.expires_at is not None and now >= row.expires_at


def _out(row: DataExport, now: datetime) -> ExportOut:
    status = "expired" if row.status == "ready" and _expired(row, now) else row.status
    return ExportOut(
        id=row.id,
        status=cast("ExportStatus", status),
        created_at=row.created_at,
        finished_at=row.finished_at,
        expires_at=row.expires_at,
        error_code=row.error_code,
    )


async def enqueue(request: Request, row: DataExport) -> None:
    queue = None
    try:
        queue = await open_queue(request.app.state.settings)
        await queue.enqueue(
            "generate_export", str(row.company_id), str(row.id), job_id=queue_id(row.id)
        )
    except Exception as exc:
        # The queued row is recovered by the minute sweep. Nothing about the export is logged.
        logger.warning("export_enqueue_deferred", kind=type(exc).__name__)
    finally:
        if queue is not None:
            await queue.close()


async def _mine(access: Access, export_id: uuid.UUID) -> DataExport:
    row = (
        await access.db.execute(
            select(DataExport).where(
                DataExport.id == export_id, DataExport.requested_by == access.caller.user_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return row


@router.post("/export", status_code=202, response_model=ExportOut)
async def request_export(request: Request, access: Exporter) -> ExportOut:
    require_step_up(access.caller.session)
    pending = (
        await access.db.execute(
            select(func.count()).select_from(DataExport).where(DataExport.status == "queued")
        )
    ).scalar_one()
    if pending:
        raise AppError(
            "EXPORT_IN_PROGRESS",
            "An export is already being prepared. It will be ready soon.",
            status_code=409,
        )
    row = DataExport(company_id=access.company_id, requested_by=access.caller.user_id)
    try:
        async with access.db.begin_nested():
            access.db.add(row)
            await access.db.flush()
    except IntegrityError as exc:
        if "uq_data_exports_one_queued" not in str(exc.orig):
            raise
        # Another request queued one at the same moment: the same answer as the check above.
        raise AppError(
            "EXPORT_IN_PROGRESS",
            "An export is already being prepared. It will be ready soon.",
            status_code=409,
        ) from None
    await access.audit("export.requested", entity_type="data_export", entity_id=row.id)
    await access.db.commit()
    await enqueue(request, row)
    return _out(row, datetime.now(UTC))


@router.get("/exports/{export_id}", response_model=ExportOut)
async def export_status(export_id: uuid.UUID, access: Exporter) -> ExportOut:
    row = await _mine(access, export_id)
    return _out(row, datetime.now(UTC))


@router.get(
    "/exports/{export_id}/download",
    status_code=302,
    responses={302: {"description": "Redirects to a 60-second link to the zip"}},
)
async def download_export(
    export_id: uuid.UUID, request: Request, access: Exporter
) -> RedirectResponse:
    row = await _mine(access, export_id)
    now = datetime.now(UTC)
    if row.status != "ready" or row.file_id is None:
        raise NotFoundError
    if _expired(row, now):
        raise AppError(
            "EXPORT_EXPIRED", "This export has expired. Ask for a new one.", status_code=410
        )
    record = await access.db.get(File, row.file_id)
    storage = request.app.state.files.storage
    if record is None or storage is None:
        raise NotFoundError
    url = storage.presign_get(record.storage_key, filename=record.original_name)
    await access.audit(
        "export.downloaded",
        entity_type="data_export",
        entity_id=row.id,
        summary=record.original_name,
    )
    await access.db.commit()
    return RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store"})
