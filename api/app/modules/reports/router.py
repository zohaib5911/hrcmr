"""Request fresh worker-generated reports; job state and links are private to their requester."""

from __future__ import annotations

import uuid  # noqa: TC003
from typing import TYPE_CHECKING, Annotated, cast

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.core.rbac_matrix import Scope
from app.integrations.storage import PRESIGN_SECONDS
from app.jobs.queue import open_queue
from app.jobs.reports import queue_id
from app.modules.identity.models import Membership
from app.modules.rbac.deps import Access, require
from app.modules.reports.models import ReportJob
from app.modules.reports.reference import ReportType  # noqa: TC001 -- FastAPI resolves annotations
from app.modules.reports.schemas import ReportJobOut

if TYPE_CHECKING:
    from app.modules.files.service import FileService
    from app.modules.reports.schemas import ReportStatus

router = APIRouter(prefix="/reports", tags=["reports"])
Reports = Annotated[Access, Depends(require("document.report.generate"))]
logger = get_logger("app.reports")


def _all(access: Access) -> None:
    if access.scope is not Scope.ALL:
        raise ForbiddenError


def _out(job: ReportJob, url: str | None = None) -> ReportJobOut:
    return ReportJobOut(
        id=job.id,
        report_type=cast("ReportType", job.report_type),
        status=cast("ReportStatus", job.status),
        created_at=job.created_at,
        finished_at=job.finished_at,
        error_code=job.error_code,
        url=url,
        expires_in=PRESIGN_SECONDS if url else None,
    )


async def enqueue(request: Request, job: ReportJob) -> None:
    queue = None
    try:
        queue = await open_queue(request.app.state.settings)
        await queue.enqueue(
            "generate_report", str(job.company_id), str(job.id), job_id=queue_id(job.id)
        )
    except Exception as exc:
        # The durable queued row is recovered by the minute sweep. No job content is logged.
        logger.warning("report_enqueue_deferred", kind=type(exc).__name__)
    finally:
        if queue is not None:
            await queue.close()


@router.get("/jobs", response_model=list[ReportJobOut])
async def recent_reports(access: Reports) -> list[ReportJobOut]:
    _all(access)
    jobs = (
        await access.db.execute(
            select(ReportJob)
            .where(ReportJob.requested_by == access.caller.user_id)
            .order_by(ReportJob.created_at.desc(), ReportJob.id.desc())
            .limit(20)
        )
    ).scalars()
    return [_out(job) for job in jobs]


@router.post("/{report_type}", status_code=202, response_model=ReportJobOut)
async def request_report(
    report_type: ReportType, request: Request, access: Reports
) -> ReportJobOut:
    _all(access)
    # Serialize the requester's pending limit with other simultaneous requests.
    await access.db.execute(
        select(Membership.id).where(Membership.user_id == access.caller.user_id).with_for_update()
    )
    pending = (
        await access.db.execute(
            select(func.count())
            .select_from(ReportJob)
            .where(ReportJob.requested_by == access.caller.user_id, ReportJob.status == "queued")
        )
    ).scalar_one()
    if pending >= 3:
        raise AppError(
            "REPORT_QUEUE_FULL",
            "Wait for a queued report to finish before requesting another.",
            status_code=429,
        )
    job = ReportJob(
        company_id=access.company_id, requested_by=access.caller.user_id, report_type=report_type
    )
    access.db.add(job)
    await access.db.flush()
    await access.audit(
        "report.requested",
        entity_type="report_job",
        entity_id=job.id,
        after={"report_type": report_type},
    )
    await access.db.commit()
    await enqueue(request, job)
    return _out(job)


@router.get("/jobs/{job_id}", response_model=ReportJobOut)
async def report_status(job_id: uuid.UUID, request: Request, access: Reports) -> ReportJobOut:
    _all(access)
    job = (
        await access.db.execute(
            select(ReportJob).where(
                ReportJob.id == job_id, ReportJob.requested_by == access.caller.user_id
            )
        )
    ).scalar_one_or_none()
    if job is None:
        raise NotFoundError
    url = None
    if job.status == "ready" and job.file_id is not None:
        files: FileService = request.app.state.files
        url, _ = await files.download_url(access, job.file_id)
    return _out(job, url)
