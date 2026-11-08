"""The job dashboard for the platform admins (T17.6, plan 8.18 Operations): the queue depth and the
failures. Every job run is in the audit trail (jobs/audit.py), and a failure is a ``job.failed``
row with no company. Retry is not here: a job's arguments are never kept, so a failed job cannot be
replayed from the log. The owner decides how that is handled (STATUS, owner actions)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.modules.audit.models import AuditEvent
from app.modules.platform_admin.schemas import JobFailureRow, JobFailuresOut

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from app.db.session import GlobalSession

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
