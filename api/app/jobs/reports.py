"""Generate report artifacts in the worker and recover durable requests after missed enqueues."""

from __future__ import annotations

import asyncio
import hashlib
import io
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.rbac_matrix import Scope, scope_for
from app.db.session import TenantSession
from app.jobs.queue import ArqQueue
from app.modules.audit.service import AuditContext, record
from app.modules.companies.models import Company
from app.modules.files.models import File
from app.modules.identity.models import Membership, User
from app.modules.reports.models import ReportJob
from app.modules.reports.projections import project
from app.modules.reports.workbooks import XLSX, workbook_bytes

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from app.integrations.storage import Storage

logger = get_logger("app.report_jobs")


def queue_id(job_id: uuid.UUID) -> str:
    # A new minute recovers a lost/crashed Redis job even while its old result key survives.
    return f"report-{job_id}-{datetime.now(UTC):%Y%m%d%H%M}"


async def _failed(engine: AsyncEngine, company_id: uuid.UUID, job_id: uuid.UUID, code: str) -> None:
    async with TenantSession(engine, company_id=company_id) as db:
        job = (
            await db.execute(select(ReportJob).where(ReportJob.id == job_id).with_for_update())
        ).scalar_one_or_none()
        if job is None or job.status != "queued":
            return
        job.status, job.error_code, job.finished_at = "failed", code, datetime.now(UTC)
        await record(
            db,
            AuditContext(company_id=company_id, actor_user_id=None, actor_type="system"),
            "report.failed",
            entity_type="report_job",
            entity_id=job.id,
            after={"report_type": job.report_type, "error_code": code},
        )
        await db.commit()


async def generate_report(ctx: dict[str, Any], company: str, report: str) -> str:
    engine: AsyncEngine = ctx["engine"]
    storage: Storage | None = ctx.get("storage")
    company_id, job_id = uuid.UUID(company), uuid.UUID(report)
    try:
        async with TenantSession(engine, company_id=company_id) as db:
            # Hold the lock through artifact/audit commit. A crash rolls back to queued; a duplicate
            # worker skips it, and the minute sweep can recover the durable request.
            job = (
                await db.execute(
                    select(ReportJob)
                    .where(ReportJob.id == job_id)
                    .with_for_update(skip_locked=True)
                )
            ).scalar_one_or_none()
            if job is None or job.status != "queued":
                return "not_queued"
            role = (
                await db.execute(
                    select(Membership.role)
                    .join(User, User.id == Membership.user_id)
                    .join(Company, Company.id == Membership.company_id)
                    .where(
                        Membership.user_id == job.requested_by,
                        Membership.status == "active",
                        User.is_active.is_(True),
                        Company.status == "active",
                    )
                )
            ).scalar_one_or_none()
            if role is None or scope_for(role, "document.report.generate") is not Scope.ALL:
                raise AppError("ACCESS_REVOKED", "Report access has changed.", status_code=403)
            if storage is None:
                raise AppError(
                    "STORAGE_NOT_CONFIGURED", "Report storage is not configured.", status_code=503
                )
            moment = datetime.now(UTC)
            sheets = await project(db, job.report_type, moment)
            content = await asyncio.to_thread(workbook_bytes, sheets)
            filename = f"{job.report_type}-{moment:%Y-%m-%d}-{job.id}.xlsx"
            key = f"company/{company_id}/{uuid.uuid4().hex}"
            artifact = File(
                company_id=company_id,
                storage_key=key,
                original_name=filename,
                mime=XLSX,
                size=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
                scan_status="clean",
                scanned_at=moment,
                owner_type="report_result",
                owner_id=job.id,
                category=job.report_type,
                uploaded_by=job.requested_by,
            )
            db.add(artifact)
            await db.flush()
            await storage.put(key, io.BytesIO(content), content_type=XLSX, size=len(content))
            job.status, job.file_id, job.finished_at = "ready", artifact.id, datetime.now(UTC)
            await record(
                db,
                AuditContext(company_id=company_id, actor_user_id=None, actor_type="system"),
                "report.generated",
                entity_type="report_job",
                entity_id=job.id,
                after={
                    "report_type": job.report_type,
                    "rows": sum(len(sheet.rows) for sheet in sheets.values()),
                },
            )
            await db.commit()
            return "ready"
    except Exception as exc:
        allowed = {"ACCESS_REVOKED", "STORAGE_NOT_CONFIGURED", "REPORT_TOO_LARGE"}
        code = exc.code if isinstance(exc, AppError) and exc.code in allowed else "REPORT_FAILED"
        logger.warning("report_generation_failed", kind=type(exc).__name__)
        await _failed(engine, company_id, job_id, code)
        return "failed"


async def sweep_report_jobs(ctx: dict[str, Any]) -> int:
    owner: AsyncEngine | None = ctx.get("owner_engine")
    if owner is None:
        return 0
    # The owner enumerates IDs only. Every report is read/generated in its own tenant session.
    async with AsyncSession(owner) as db:
        waiting = (
            await db.execute(
                select(ReportJob.company_id, ReportJob.id)
                .where(ReportJob.status == "queued")
                .order_by(ReportJob.created_at)
                .limit(100)
            )
        ).all()
    queue = ArqQueue(ctx["redis"])
    for company_id, job_id in waiting:
        await queue.enqueue(
            "generate_report", str(company_id), str(job_id), job_id=queue_id(job_id)
        )
    return len(waiting)
