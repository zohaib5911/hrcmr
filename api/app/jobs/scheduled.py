"""The scheduled jobs (plan.md T2.9): when each one runs, and what it does.

The times are UTC. A job whose work belongs to a company's own calendar (reminders, right-to-work
status) works out each company's local day itself. Jobs that later tasks give real work to are
registered now, so the schedule is in one place; until then each reports that it handled nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from arq import cron as arq_cron
from arq import func

from app.jobs.audit import tracked
from app.jobs.cloudflare import cloudflare_ranges_weekly
from app.jobs.compliance import reminders_daily, rtw_status_daily
from app.jobs.deletion import deletion_executor_hourly
from app.jobs.email import deliver_email, sweep_email_outbox
from app.jobs.exports import generate_export, sweep_export_jobs
from app.jobs.holidays import bank_holidays_weekly
from app.jobs.learning import learning_overdue_daily
from app.jobs.notifications import notifications_digest_daily
from app.jobs.policies import policies_overdue_daily
from app.jobs.reports import generate_report, sweep_report_jobs
from app.jobs.rules import rules_watch_daily
from app.modules.email.outbox import MAX_ATTEMPTS
from app.modules.files.service import remove_orphans

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from arq.cron import CronJob
    from arq.worker import Function


async def worker_ping(ctx: dict[str, Any]) -> str:
    """Proves the worker is taking jobs: the API's readiness check and the tests enqueue it."""
    return "pong"


async def files_orphans_daily(ctx: dict[str, Any]) -> int:
    """Delete stored files that no ``files`` row points to (T2.7)."""
    storage, owner = ctx.get("storage"), ctx.get("owner_engine")
    if storage is None or owner is None:
        return 0
    return await remove_orphans(storage, owner)


def _nothing_yet(name: str) -> Callable[[dict[str, Any]], Awaitable[int]]:
    async def job(ctx: dict[str, Any]) -> int:
        return 0

    job.__name__ = name
    return job


@dataclass(frozen=True)
class Schedule:
    name: str
    job: Callable[..., Awaitable[Any]]
    when: dict[str, Any]  # arq cron fields: weekday, hour, minute (UTC)
    task: str  # the plan task that gives it its work
    quiet: bool = False


SCHEDULE: tuple[Schedule, ...] = (
    Schedule("backups_nightly", _nothing_yet("backups_nightly"), {"hour": 1, "minute": 0}, "T20.2"),
    Schedule(
        "retention_purge_daily",
        _nothing_yet("retention_purge_daily"),
        {"hour": 2, "minute": 0},
        "T16.5",
    ),
    Schedule("files_orphans_daily", files_orphans_daily, {"hour": 2, "minute": 30}, "T2.7"),
    Schedule(
        "bank_holidays_weekly",
        bank_holidays_weekly,
        {"weekday": "mon", "hour": 3, "minute": 0},
        "T4.5",
    ),
    Schedule(
        "cloudflare_ranges_weekly",
        cloudflare_ranges_weekly,
        {"weekday": "mon", "hour": 3, "minute": 10},
        "T4.5",
    ),
    Schedule("register_ingest", _nothing_yet("register_ingest"), {"hour": 3, "minute": 30}, "T4.2"),
    Schedule("rtw_status_daily", rtw_status_daily, {"hour": 5, "minute": 0}, "T7.4"),
    Schedule("reminders_daily", reminders_daily, {"hour": 6, "minute": 0}, "T7.4"),
    Schedule("policies_overdue_daily", policies_overdue_daily, {"hour": 6, "minute": 15}, "T10.3"),
    Schedule("learning_overdue", learning_overdue_daily, {"hour": 6, "minute": 15}, "T13.3"),
    Schedule("notifications_digest", notifications_digest_daily, {"hour": 7, "minute": 0}, "T14.2"),
    Schedule("rules_watch_daily", rules_watch_daily, {"hour": 7, "minute": 0}, "T15.7"),
    Schedule(
        "deletion_executor_hourly",
        deletion_executor_hourly,
        {"minute": 15},
        "T16.5",
    ),
    Schedule("report_jobs_sweep", sweep_report_jobs, {}, "T10.2", quiet=True),
    Schedule("export_jobs_sweep", sweep_export_jobs, {}, "T16.4", quiet=True),
    Schedule("email_outbox_sweep", sweep_email_outbox, {}, "T2.8", quiet=True),  # every minute
)


def cron_jobs() -> list[CronJob]:
    return [
        arq_cron(tracked(s.job, name=s.name, quiet=s.quiet), name=s.name, **s.when)
        for s in SCHEDULE
    ]


def functions() -> list[Function]:
    """What can be enqueued by name (the cron jobs are registered separately)."""
    return [
        # Our own retry schedule decides when to try again, so the worker allows one more run.
        func(
            tracked(deliver_email, name="deliver_email", quiet=True),
            name="deliver_email",
            max_tries=MAX_ATTEMPTS + 1,
        ),
        func(tracked(generate_report, name="generate_report"), name="generate_report", max_tries=1),
        func(tracked(generate_export, name="generate_export"), name="generate_export", max_tries=1),
        func(tracked(worker_ping, name="worker_ping", quiet=True), name="worker_ping", max_tries=1),
    ]
