"""T2.9: the worker starts, takes a queued job and finishes it; the schedule holds every job the plan
names; and each job run, and each failure, is logged and enters the audit trail."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
from arq import func
from arq.connections import ArqRedis
from arq.jobs import Job
from arq.worker import Worker
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.pool import NullPool

from app.core.crypto import KeyRing, set_keyring
from app.integrations.email import Message
from app.jobs.audit import JobAudit, tracked
from app.jobs.queue import ArqQueue, open_queue
from app.jobs.scheduled import SCHEDULE, cron_jobs, functions
from app.modules.email.outbox import EmailDelivery, OutboxMailer
from tests.db.support import DatabaseUnderTest, engine_for
from tests.support import TEST_REDIS_URL, build_settings

SETTINGS = build_settings(redis_url=TEST_REDIS_URL)
PLAN_JOBS = {
    "reminders_daily",
    "rtw_status_daily",
    "register_ingest",
    "bank_holidays_weekly",
    "rules_watch_daily",
    "retention_purge_daily",
    "backups_nightly",
    "deletion_executor_hourly",
}


@pytest.fixture(autouse=True)
def _keys() -> Any:
    set_keyring(KeyRing(keys={"k1": os.urandom(32)}, active_kid="k1", blind_key=os.urandom(32)))
    yield
    set_keyring(None)


class Mailbox:
    def __init__(self) -> None:
        self.sent: list[Message] = []

    async def send(self, message: Message) -> str | None:
        self.sent.append(message)
        return "id-1"


async def boom(ctx: dict[str, Any]) -> None:
    raise RuntimeError("secret detail that must not reach the audit trail")


@pytest.fixture
async def rig(database: DatabaseUnderTest) -> AsyncIterator[dict[str, Any]]:
    redis = Redis.from_url(TEST_REDIS_URL)
    await redis.flushdb()
    owner = engine_for(database.owner_url, poolclass=NullPool)
    app_engine = engine_for(database.app_url, poolclass=NullPool)
    queue = await open_queue(SETTINGS)
    mailbox = Mailbox()
    ctx = {
        "audit": JobAudit(owner),
        "email": EmailDelivery(app_engine, mailbox, SETTINGS),
        "owner_engine": owner,
        "storage": None,
    }

    async def run(*, extra: list[Any] | None = None) -> Worker:
        worker = Worker(
            functions=[
                *functions(),
                *(func(tracked(s.job, name=s.name, quiet=s.quiet), name=s.name) for s in SCHEDULE),
                *(extra or []),
            ],
            # Queue-focused tests must not start unrelated jobs at a wall-clock minute boundary.
            # The schedule and registered cron names are checked separately below.
            cron_jobs=[],
            redis_pool=queue._pool,
            burst=True,
            handle_signals=False,
            ctx=ctx,
            poll_delay=0.05,
        )
        await worker.async_run()  # runs what is queued, then stops (the pool is closed below)
        return worker

    yield {
        "run": run,
        "queue": queue,
        "pool": queue._pool,
        "owner": owner,
        "engine": app_engine,
        "mailbox": mailbox,
    }
    await queue.close()
    await redis.flushdb()
    await redis.aclose()
    await owner.dispose()
    await app_engine.dispose()


async def _events(owner: AsyncEngine, job_id: str) -> list[Any]:
    async with owner.connect() as c:
        result = await c.execute(
            text(
                "select action, company_id, actor_type, after from audit_events "
                "where entity_type = 'job' and after ->> 'job_id' = :j"
            ),
            {"j": job_id},
        )
        return list(result.mappings())


def test_the_schedule_holds_every_job_the_plan_names() -> None:
    names = {s.name for s in SCHEDULE}
    assert names >= PLAN_JOBS
    assert {"files_orphans_daily", "email_outbox_sweep"} <= names
    assert len(names) == len(SCHEDULE)
    assert {job.name for job in cron_jobs()} == names


async def test_the_worker_starts_and_runs_a_sample_job(rig: dict[str, Any]) -> None:
    pool: ArqRedis = rig["pool"]
    job = await pool.enqueue_job("worker_ping")
    assert job is not None
    worker = await rig["run"]()
    assert worker.jobs_complete == 1
    assert worker.jobs_failed == 0
    assert await Job(job.job_id, pool).result() == "pong"


async def test_a_run_is_audited_and_a_failure_is_audited_without_its_detail(
    rig: dict[str, Any],
) -> None:
    pool: ArqRedis = rig["pool"]
    ran = await pool.enqueue_job("files_orphans_daily")
    broke = await pool.enqueue_job("boom")
    assert ran is not None
    assert broke is not None
    worker = await rig["run"](extra=[func(tracked(boom, name="boom"), name="boom", max_tries=1)])
    assert worker.jobs_failed == 1

    (finished,) = await _events(rig["owner"], ran.job_id)
    assert finished["action"] == "job.finished"
    assert finished["company_id"] is None
    assert finished["actor_type"] == "system"
    assert finished["after"]["job"] == "files_orphans_daily"
    assert finished["after"]["handled"] == 0

    (failed,) = await _events(rig["owner"], broke.job_id)
    assert failed["action"] == "job.failed"
    assert failed["after"]["kind"] == "RuntimeError"
    assert "secret detail" not in str(failed["after"])


async def test_an_email_queued_by_the_api_is_sent_by_the_worker(rig: dict[str, Any]) -> None:
    mailer = OutboxMailer(rig["engine"], ArqQueue(rig["pool"]))
    await mailer.send_template(
        to="amira@example.com", template="password_changed", data={"first_name": "Amira"}
    )
    worker = await rig["run"]()
    assert worker.jobs_complete == 1
    (message,) = rig["mailbox"].sent
    assert message.subject == "Your password was changed"
