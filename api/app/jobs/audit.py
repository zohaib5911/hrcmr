"""Every job run is logged, and every failure (and every run that matters) enters the audit trail.

ARQ does not tell a job hook which function is running, so each job is wrapped. The wrapper logs
start, end and failure with the job's name, id, try number and duration (never its arguments or
its result, which may hold personal data), and records the audit event.
"""

from __future__ import annotations

import functools
import time
from typing import TYPE_CHECKING, Any

from arq import Retry
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.audit.service import AuditContext, record

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from arq.typing import WorkerCoroutine
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger("app.jobs")


class JobAudit:
    """Writes job events (they belong to the platform, not to a company) as the table owner."""

    def __init__(self, engine: AsyncEngine | None) -> None:
        self._engine = engine

    async def record(self, action: str, job: str, details: dict[str, Any]) -> None:
        if self._engine is None:
            return  # no owner connection on this machine: the log line is all there is
        try:
            async with AsyncSession(self._engine, expire_on_commit=False) as db:
                await record(
                    db,
                    AuditContext(company_id=None, actor_user_id=None, actor_type="system"),
                    action,
                    entity_type="job",
                    summary=job,
                    after={"job": job, **details},
                )
                await db.commit()
        except Exception as exc:  # a failed audit write must not fail, or re-run, the job itself
            logger.error("job_audit_failed", job=job, kind=type(exc).__name__)


def tracked(
    function: Callable[..., Awaitable[Any]], *, name: str, quiet: bool = False
) -> WorkerCoroutine:
    """Wrap ``function`` so its runs are logged and audited. ``quiet`` jobs (they run every minute
    or per e-mail) are audited only when they fail."""

    @functools.wraps(function)
    async def run(ctx: dict[str, Any], *args: Any) -> Any:
        audit: JobAudit = ctx.get("audit") or JobAudit(None)
        started = time.monotonic()
        details = {"job_id": ctx.get("job_id"), "try": ctx.get("job_try")}
        logger.info("job_started", job=name, **details)
        try:
            result = await function(ctx, *args)
        except Retry:
            logger.info("job_will_retry", job=name, **details)
            raise
        except Exception as exc:
            seconds = round(time.monotonic() - started, 3)
            logger.error(
                "job_failed", job=name, kind=type(exc).__name__, seconds=seconds, **details
            )
            await audit.record(
                "job.failed", name, {**details, "kind": type(exc).__name__, "seconds": seconds}
            )
            raise
        seconds = round(time.monotonic() - started, 3)
        logger.info("job_finished", job=name, seconds=seconds, **details)
        if not quiet:
            handled = result if isinstance(result, int) and not isinstance(result, bool) else None
            await audit.record(
                "job.finished", name, {**details, "seconds": seconds, "handled": handled}
            )
        return result

    run.__name__ = name
    return run
