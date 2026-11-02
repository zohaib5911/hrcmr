"""The background worker (plan.md T2.9): ``python -m app.jobs.worker``.

It runs on its own, as a second service built from the same image as the API with the same
variables. It takes jobs the API queues (sending an e-mail) and runs the schedule in
``app.jobs.scheduled``. ARQ makes sure a scheduled job runs once even with several workers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from arq.worker import run_worker
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings, get_settings
from app.core.crypto import KeyRing, set_keyring
from app.core.logging import configure_logging, get_logger
from app.db.engine import create_engine
from app.integrations.email import NoTransport, transport_from_settings
from app.integrations.storage import Storage
from app.jobs.audit import JobAudit
from app.jobs.holidays import bank_holidays_weekly
from app.jobs.queue import redis_settings
from app.jobs.scheduled import cron_jobs, functions
from app.modules.email.outbox import EmailDelivery

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = get_logger("app.worker")


def build_context(settings: Settings) -> dict[str, Any]:
    """What jobs use, built once when the worker starts."""
    engine = create_engine(settings)
    owner_engine: AsyncEngine | None = (
        create_async_engine(
            settings.database_url_owner.get_secret_value(), pool_size=2, hide_parameters=True
        )
        if settings.database_url_owner
        else None
    )
    return {
        "settings": settings,
        "engine": engine,
        "owner_engine": owner_engine,
        "storage": Storage.from_settings(settings),
        "email": EmailDelivery(
            engine, transport_from_settings(settings) or NoTransport(), settings
        ),
        "audit": JobAudit(owner_engine),
    }


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    set_keyring(KeyRing.from_settings(settings))
    ctx.update(build_context(settings))
    logger.info("worker_started", app_env=settings.app_env.value)
    # A new deployment has no public holidays until the weekly run: fetch them now, once.
    await bank_holidays_weekly(ctx)


async def shutdown(ctx: dict[str, Any]) -> None:
    for name in ("engine", "owner_engine"):
        if ctx.get(name) is not None:
            await ctx[name].dispose()
    logger.info("worker_stopped")


class WorkerSettings:
    functions = functions()
    cron_jobs = cron_jobs()
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 600  # seconds; the longest job (a backup, a data export) gets its own limit later
    keep_result = 3600
    health_check_interval = 30


def main() -> None:
    configure_logging()
    run_worker(WorkerSettings, redis_settings=redis_settings(get_settings()))  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
