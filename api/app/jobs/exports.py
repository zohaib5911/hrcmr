"""Build a company's data export in the worker (T16.4), and recover requests after a missed enqueue.

The request is queued; the worker re-checks that the requester still may export before it reads
anything. The zip is a private file, and its link is valid for 7 days from when it was made.
"""

from __future__ import annotations

import json
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt
from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.rbac_matrix import Scope, scope_for
from app.db.session import TenantSession
from app.jobs.queue import ArqQueue
from app.modules.audit.service import AuditContext, record
from app.modules.companies.models import Company
from app.modules.email.models import EmailOutbox
from app.modules.email.outbox import PAYLOAD_CONTEXT
from app.modules.email.templates import check
from app.modules.exports.archive import ZIP, digest, write_archive
from app.modules.exports.models import DataExport
from app.modules.files.models import File
from app.modules.identity.models import Membership, User

if TYPE_CHECKING:
    from typing import BinaryIO

    from sqlalchemy.ext.asyncio import AsyncEngine

    from app.integrations.storage import Storage

logger = get_logger("app.exports")

EXPORT_DAYS = 7
SPOOL_BYTES = 32 * 1024 * 1024  # a larger zip spills from memory to disk
DOWNLOAD_PATH = "/api/v1/companies/me/exports/{export_id}/download"


def queue_id(export_id: uuid.UUID) -> str:
    # A new minute recovers a lost or crashed Redis job even while its old result key survives.
    return f"export-{export_id}-{datetime.now(UTC):%Y%m%d%H%M}"


async def _failed(
    engine: AsyncEngine, company_id: uuid.UUID, export_id: uuid.UUID, code: str
) -> None:
    async with TenantSession(engine, company_id=company_id) as db:
        row = (
            await db.execute(select(DataExport).where(DataExport.id == export_id).with_for_update())
        ).scalar_one_or_none()
        if row is None or row.status != "queued":
            return
        row.status, row.error_code, row.finished_at = "failed", code, datetime.now(UTC)
        await record(
            db,
            AuditContext(company_id=company_id, actor_user_id=None, actor_type="system"),
            "export.failed",
            entity_type="data_export",
            entity_id=row.id,
            after={"error_code": code},
        )
        await db.commit()


async def _requester(db: AsyncSession, company_id: uuid.UUID, user_id: uuid.UUID) -> Any:
    """The requester's role, if they are still an active member of the company."""
    return (
        await db.execute(
            select(Membership.role)
            .join(User, User.id == Membership.user_id)
            .join(Company, Company.id == Membership.company_id)
            .where(
                Membership.user_id == user_id,
                Membership.company_id == company_id,
                Membership.status == "active",
                User.is_active.is_(True),
                Company.status == "active",
            )
        )
    ).scalar_one_or_none()


async def generate_export(ctx: dict[str, Any], company: str, export: str) -> str:
    engine: AsyncEngine = ctx["engine"]
    storage: Storage | None = ctx.get("storage")
    settings = ctx["settings"]  # the worker's startup puts the settings in the context
    company_id, export_id = uuid.UUID(company), uuid.UUID(export)
    try:
        async with TenantSession(engine, company_id=company_id) as db:
            # Hold the lock until the file and the audit row commit. A crash rolls back to queued,
            # and a duplicate worker skips it; the minute sweep recovers a lost request.
            row = (
                await db.execute(
                    select(DataExport)
                    .where(DataExport.id == export_id)
                    .with_for_update(skip_locked=True)
                )
            ).scalar_one_or_none()
            if row is None or row.status != "queued":
                return "not_queued"
            role = await _requester(db, company_id, row.requested_by)
            if role is None or scope_for(role, "company.export") is not Scope.ALL:
                raise AppError("ACCESS_REVOKED", "Export access has changed.", status_code=403)
            if storage is None:
                raise AppError(
                    "STORAGE_NOT_CONFIGURED", "Export storage is not configured.", status_code=503
                )
            moment = datetime.now(UTC)
            company_row = await db.get(Company, company_id)
            requester = await db.get(User, row.requested_by)
            if company_row is None or requester is None:
                raise AppError("ACCESS_REVOKED", "Export access has changed.", status_code=403)
            with tempfile.SpooledTemporaryFile(max_size=SPOOL_BYTES) as spool:
                # A spooled file is binary: it stays in memory until it grows past SPOOL_BYTES.
                body = cast("BinaryIO", spool)
                await write_archive(db, storage, company_id, company_row.name, moment, body)
                size = spool.seek(0, 2)
                sha256 = digest(body)
                key = f"company/{company_id}/{uuid.uuid4().hex}"
                await storage.put(key, body, content_type=ZIP, size=size)
            artifact = File(
                company_id=company_id,
                storage_key=key,
                original_name=f"data-export-{moment:%Y-%m-%d}-{row.id}.zip",
                mime=ZIP,
                size=size,
                sha256=sha256,
                scan_status="clean",
                scanned_at=moment,
                owner_type="data_export",
                owner_id=row.id,
                category="data_export",
                uploaded_by=row.requested_by,
            )
            db.add(artifact)
            await db.flush()
            expires = moment + timedelta(days=EXPORT_DAYS)
            row.status, row.file_id, row.finished_at = "ready", artifact.id, moment
            row.expires_at = expires
            await record(
                db,
                AuditContext(company_id=company_id, actor_user_id=None, actor_type="system"),
                "export.generated",
                entity_type="data_export",
                entity_id=row.id,
                after={"bytes": size},
            )
            link = f"{settings.api_origin}{DOWNLOAD_PATH.format(export_id=row.id)}"
            data = {
                "first_name": requester.first_name,
                "expires_on": f"{expires:%-d %B %Y}",
                "link": link,
            }
            check("data_export_ready", data)
            # Sent to the requester only, whatever their e-mail preference: they asked for it.
            db.add(
                EmailOutbox(
                    to_address=requester.email,
                    template="data_export_ready",
                    payload=encrypt(json.dumps(data), context=PAYLOAD_CONTEXT),
                )
            )
            await db.commit()
            return "ready"
    except Exception as exc:
        allowed = {"ACCESS_REVOKED", "STORAGE_NOT_CONFIGURED"}
        code = exc.code if isinstance(exc, AppError) and exc.code in allowed else "EXPORT_FAILED"
        logger.warning("export_generation_failed", kind=type(exc).__name__)
        await _failed(engine, company_id, export_id, code)
        return "failed"


async def sweep_export_jobs(ctx: dict[str, Any]) -> int:
    owner: AsyncEngine | None = ctx.get("owner_engine")
    if owner is None:
        return 0
    # The owner enumerates IDs only. Each export is read and built in its own tenant session.
    async with AsyncSession(owner) as db:
        waiting = (
            await db.execute(
                select(DataExport.company_id, DataExport.id)
                .where(DataExport.status == "queued")
                .order_by(DataExport.created_at)
                .limit(100)
            )
        ).all()
    queue = ArqQueue(ctx["redis"])
    for company_id, export_id in waiting:
        await queue.enqueue(
            "generate_export", str(company_id), str(export_id), job_id=queue_id(export_id)
        )
    return len(waiting)
