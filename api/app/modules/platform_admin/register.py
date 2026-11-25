"""Sponsor register operations: global read status and safe, audited import reruns (T20.5)."""

from __future__ import annotations

import uuid  # noqa: TC003
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.core.errors import AppError
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import AuditContext, record
from app.modules.platform_admin.jobs import enqueue_rerun
from app.modules.platform_admin.schemas import (
    JobFailureRow,
    JobRerunOut,
    RegisterPublicationOut,
    RegisterStatusOut,
)
from app.modules.register.ingest import APPROVED, COMPLETE, HELD
from app.modules.register.models import Publication, Sponsor

if TYPE_CHECKING:
    from app.db.session import GlobalSession
    from app.jobs.queue import ArqQueue


async def status(db: GlobalSession) -> RegisterStatusOut:
    publication = await db.scalar(
        select(Publication)
        .where(Publication.status == COMPLETE)
        .order_by(Publication.fetched_at.desc(), Publication.id.desc())
        .limit(1)
    )
    held = await db.scalar(
        select(Publication)
        .where(Publication.status.in_((HELD, APPROVED)))
        .order_by(Publication.fetched_at.desc(), Publication.id.desc())
        .limit(1)
    )
    errors = await db.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.action == "job.failed",
            AuditEvent.company_id.is_(None),
            AuditEvent.actor_type == "system",
            AuditEvent.summary == "register_ingest",
        )
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(20)
    )
    return RegisterStatusOut(
        last_publication=(
            RegisterPublicationOut.model_validate(publication, from_attributes=True)
            if publication
            else None
        ),
        held_import=(
            RegisterPublicationOut.model_validate(held, from_attributes=True) if held else None
        ),
        current_sponsors=int(
            await db.scalar(select(func.count(Sponsor.id)).where(Sponsor.current)) or 0
        ),
        total_sponsors=int(await db.scalar(select(func.count(Sponsor.id))) or 0),
        errors=[
            JobFailureRow(
                id=event.id,
                created_at=event.created_at,
                job="register_ingest",
                detail=dict(event.after or {}),
            )
            for event in errors
        ],
    )


async def run(
    db: GlobalSession, context: AuditContext, *, reason: str, queue: ArqQueue
) -> JobRerunOut:
    made = await enqueue_rerun("register_ingest", queue)
    await record(
        db,
        context,
        "platform.register_rerun",
        entity_type="job",
        after={"job": made.job, "job_id": made.job_id},
        reason=reason,
        summary="Re-run sponsor register import",
    )
    return made


async def approve_hold(
    db: GlobalSession,
    context: AuditContext,
    publication_id: uuid.UUID,
    *,
    reason: str,
    queue: ArqQueue,
) -> JobRerunOut:
    """A platform admin confirms a held import is a genuine reduction (ISS-11); the re-run that
    follows applies it, since the same file is then approved."""
    held = await db.get(Publication, publication_id, with_for_update=True)
    if held is None or held.status != HELD:
        raise AppError("NOT_HELD", "There is no held import with that id.", status_code=404)
    held.status = APPROVED
    made = await enqueue_rerun("register_ingest", queue)
    await record(
        db,
        context,
        "platform.register_hold_approved",
        entity_type="register_publication",
        entity_id=held.id,
        after={"job": made.job, "job_id": made.job_id, "row_count": held.row_count},
        reason=reason,
        summary="Approved a held sponsor register import",
    )
    return made
