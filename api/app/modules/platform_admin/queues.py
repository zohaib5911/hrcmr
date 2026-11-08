"""The deletion and export request queues for the platform admins (T17.4, plan 8.16 and 8.18).

Read only. A company asks for its account to be deleted (T16.5) or for its data export (T16.4);
the queues show where each request stands. The deletion code hash is never read. Nothing here
changes a request: the purge runs from its job (app/jobs/deletion.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, func, select

from app.modules.companies.models import Company
from app.modules.deletion.models import DeletionRequest
from app.modules.exports.models import DataExport
from app.modules.platform_admin.schemas import (
    DataExportRow,
    DataExportsOut,
    DeletionRequestRow,
    DeletionRequestsOut,
)

if TYPE_CHECKING:
    from app.db.session import GlobalSession

PAGE_MAX = 100
DELETION_STATUSES = ("awaiting_code", "scheduled", "withdrawn", "completed")
EXPORT_STATUSES = ("queued", "ready", "failed")


def _deletion_status(request: DeletionRequest) -> str:
    if request.completed_at is not None:
        return "completed"
    if request.withdrawn_at is not None:
        return "withdrawn"
    if request.confirmed_at is not None:
        return "scheduled"
    return "awaiting_code"


def _deletion_filter(status: str) -> Any:
    """The same states as ``_deletion_status``, as a condition the database can filter on."""
    if status == "completed":
        return DeletionRequest.completed_at.is_not(None)
    if status == "withdrawn":
        return DeletionRequest.withdrawn_at.is_not(None)
    open_request = and_(
        DeletionRequest.withdrawn_at.is_(None), DeletionRequest.completed_at.is_(None)
    )
    if status == "scheduled":
        return and_(open_request, DeletionRequest.confirmed_at.is_not(None))
    return and_(open_request, DeletionRequest.confirmed_at.is_(None))


async def deletion_requests(
    db: GlobalSession, *, status: str | None, limit: int, offset: int
) -> DeletionRequestsOut:
    query = select(DeletionRequest, Company.name).join(
        Company, Company.id == DeletionRequest.company_id
    )
    count = select(func.count(DeletionRequest.id))
    if status:
        query = query.where(_deletion_filter(status))
        count = count.where(_deletion_filter(status))
    total = await db.scalar(count)
    rows = await db.execute(
        query.order_by(DeletionRequest.created_at.desc(), DeletionRequest.id)
        .limit(limit)
        .offset(offset)
    )
    items = [
        DeletionRequestRow(
            id=request.id,
            company_id=request.company_id,
            company_name=name,
            status=_deletion_status(request),
            requested_at=request.created_at,
            scheduled_for=request.scheduled_for,
            withdrawn_at=request.withdrawn_at,
            completed_at=request.completed_at,
            export_requested=request.export_requested,
        )
        for request, name in rows.all()
    ]
    return DeletionRequestsOut(items=items, total=int(total or 0))


async def data_exports(
    db: GlobalSession, *, status: str | None, limit: int, offset: int
) -> DataExportsOut:
    query = select(DataExport, Company.name).join(Company, Company.id == DataExport.company_id)
    count = select(func.count(DataExport.id))
    if status:
        query = query.where(DataExport.status == status)
        count = count.where(DataExport.status == status)
    total = await db.scalar(count)
    rows = await db.execute(
        query.order_by(DataExport.created_at.desc(), DataExport.id).limit(limit).offset(offset)
    )
    items = [
        DataExportRow(
            id=export.id,
            company_id=export.company_id,
            company_name=name,
            status=export.status,
            requested_at=export.created_at,
            finished_at=export.finished_at,
            expires_at=export.expires_at,
            error_code=export.error_code,
        )
        for export, name in rows.all()
    ]
    return DataExportsOut(items=items, total=int(total or 0))
