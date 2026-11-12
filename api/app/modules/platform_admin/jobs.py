"""The job dashboard for the platform admins (T17.6, plan 8.18 Operations): the queue depth and the
failures. Every job run is in the audit trail (jobs/audit.py), and a failure is a ``job.failed``
row with no company. Retry is not here: a job's arguments are never kept, so a failed job cannot be
replayed from the log. The owner decides how that is handled (STATUS, owner actions)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.core.errors import AppError, NotFoundError
from app.jobs.rerun import RERUNNABLE, rerun_name
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import AuditContext, record
from app.modules.platform_admin.schemas import JobFailureRow, JobFailuresOut, JobRerunOut

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from app.db.session import GlobalSession
    from app.jobs.queue import ArqQueue

# ARQ's default queue: a sorted set of the jobs waiting to run.
QUEUE_KEY = "arq:queue"
PAGE_MAX = 200
_FAILED = (
    AuditEvent.action == "job.failed",
    AuditEvent.company_id.is_(None),
    AuditEvent.actor_type == "system",
)


async def failures(db: GlobalSession, *, limit: int, offset: int) -> JobFailuresOut:
    total = await db.scalar(select(func.count(AuditEvent.id)).where(*_FAILED))
    found = await db.execute(
        select(AuditEvent)
        .where(*_FAILED)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(limit)
        .offset(offset)
    )
    items = [
        JobFailureRow(
            id=event.id,
            created_at=event.created_at,
            job=event.summary or "",
            detail=_detail(event.after),
        )
        for event in found.scalars().all()
    ]
    return JobFailuresOut(items=items, total=int(total or 0))


def _detail(after: dict[str, Any] | None) -> dict[str, Any]:
    """The run's facts (try, kind, seconds, id). The job's arguments are never in the log."""
    return dict(after or {})


async def waiting(redis: Redis) -> int:
    """How many jobs are queued and waiting for a worker."""
    return int(await redis.zcard(QUEUE_KEY))


async def rerun(
    db: GlobalSession,
    context: AuditContext,
    failure_id: uuid.UUID,
    *,
    reason: str,
    queue: ArqQueue,
) -> JobRerunOut:
    """Queue one more run of a failed job, if the job is on the re-run list (app/jobs/rerun.py).

    The run is queued before the audit row is written, and the caller commits. If the commit fails,
    the job still runs once more, which the list allows; a retry never sends mail."""
    failed = (
        await db.execute(
            select(AuditEvent).where(
                AuditEvent.id == failure_id,
                *_FAILED,
            )
        )
    ).scalar_one_or_none()
    if failed is None:
        raise NotFoundError("We could not find that failed run.")
    job = failed.summary or ""
    made = await enqueue_rerun(job, queue)
    await record(
        db,
        context,
        "platform.job_rerun",
        entity_type="job",
        after={"job": job, "failure": str(failure_id), "job_id": made.job_id},
        reason=reason,
        summary=f"Re-run {job} after a failure",
    )
    return made


async def enqueue_rerun(job: str, queue: ArqQueue) -> JobRerunOut:
    """All admin-triggered runs pass the same no-arguments, no-messages allow-list."""
    if job not in RERUNNABLE:
        raise AppError(
            "NOT_RERUNNABLE",
            "This job cannot be run again from here. It sends mail or needs its arguments: "
            "re-run the action it belongs to instead.",
            status_code=409,
        )
    job_id = f"rerun-{uuid.uuid4().hex}"
    await queue.enqueue(rerun_name(job), job_id=job_id)
    return JobRerunOut(job=job, job_id=job_id)
