"""T17.6: the job dashboard. Platform admins see how many jobs wait and every recorded failure,
with the run's facts and never its arguments. A company administrator sees none of it. Retry is
not offered: a job's arguments are not kept, so a failure cannot be replayed from the log.

The rig flushes Redis for every test, so the queue depth is exact."""

from __future__ import annotations

import json
import uuid
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text

from app.jobs.rerun import RERUNNABLE
from app.jobs.scheduled import functions
from tests.db.test_employee_documents import rig as rig
from tests.support import TEST_REDIS_URL, step_up

API = "/api/v1"


async def _platform_admin(rig: dict[str, Any], level: str) -> Any:
    """A signed-in company administrator made a platform admin at ``level``, with MFA, and the
    platform cookie started, as the admin pages need (T17.1)."""
    admin = await rig["person"]("company_admin", rig["a"])
    me = uuid.UUID((await admin.get(f"{API}/auth/me")).json()["user"]["id"])
    async with rig["owner"].begin() as c:
        await c.execute(
            text("insert into platform_admins (user_id, level) values (:u, :l)"),
            {"u": me, "l": level},
        )
        await c.execute(text("update users set mfa_enabled=true where id=:u"), {"u": me})
    await step_up(admin)
    started = await admin.post(f"{API}/auth/platform-session")
    assert started.status_code == 201, started.text
    return admin


async def test_only_a_platform_admin_reads_the_job_dashboard(rig: dict[str, Any]) -> None:
    company_admin = await rig["person"]("company_admin", rig["a"])
    assert (await company_admin.get(f"{API}/platform/jobs/failures")).status_code == 403
    assert (await company_admin.get(f"{API}/platform/jobs/queue")).status_code == 403


async def test_a_failure_shows_the_run_and_never_its_arguments(rig: dict[str, Any]) -> None:
    job = f"deletion_job_{uuid.uuid4().hex[:8]}"
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "insert into audit_events (id, company_id, actor_type, action, entity_type, "
                "summary, after) values (:i, null, 'system', 'job.failed', 'job', :job, "
                "cast(:after as jsonb))"
            ),
            {
                "i": uuid.uuid4(),
                "job": job,
                "after": json.dumps(
                    {"job": job, "try": 2, "kind": "TimeoutError", "seconds": 4.5, "id": "run-9"}
                ),
            },
        )
    admin = await _platform_admin(rig, "support")
    failures = (await admin.get(f"{API}/platform/jobs/failures?limit=200")).json()
    [row] = [item for item in failures["items"] if item["job"] == job]
    assert row["detail"]["kind"] == "TimeoutError"
    assert row["detail"]["try"] == 2
    assert "args" not in row["detail"]
    assert "arguments" not in row["detail"]


async def test_the_queue_depth_is_the_number_of_waiting_jobs(rig: dict[str, Any]) -> None:
    redis = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    try:
        await redis.zadd("arq:queue", {"job-a": 1, "job-b": 2})
        admin = await _platform_admin(rig, "support")
        queue = await admin.get(f"{API}/platform/jobs/queue")
        assert queue.status_code == 200, queue.text
        assert queue.json() == {"waiting": 2}
    finally:
        await redis.aclose()


async def _seed_failure(rig: dict[str, Any], job: str) -> uuid.UUID:
    failure = uuid.uuid4()
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "insert into audit_events (id, company_id, actor_type, action, entity_type, "
                "summary, after) values (:i, null, 'system', 'job.failed', 'job', :job, "
                "cast(:after as jsonb))"
            ),
            {
                "i": failure,
                "job": job,
                "after": json.dumps({"job": job, "try": 1, "kind": "TimeoutError", "seconds": 1.0}),
            },
        )
    return failure


async def test_an_allow_listed_failure_is_queued_once_more_and_audited(rig: dict[str, Any]) -> None:
    failure = await _seed_failure(rig, "rtw_status_daily")
    admin = await _platform_admin(rig, "support")
    made = await admin.post(
        f"{API}/platform/jobs/failures/{failure}/rerun",
        json={"reason": "Worker was down overnight"},
    )
    assert made.status_code == 202, made.text
    assert made.json()["job"] == "rtw_status_daily"
    assert (await admin.get(f"{API}/platform/jobs/queue")).json() == {"waiting": 1}
    async with rig["owner"].connect() as c:
        reason = (
            await c.execute(
                text(
                    "select reason from audit_events where action = 'platform.job_rerun' "
                    "and after->>'failure' = :f"
                ),
                {"f": str(failure)},
            )
        ).scalar_one()
    assert reason == "Worker was down overnight"


async def test_a_job_that_sends_mail_is_refused_and_nothing_is_queued(rig: dict[str, Any]) -> None:
    failure = await _seed_failure(rig, "reminders_daily")
    admin = await _platform_admin(rig, "support")
    refused = await admin.post(
        f"{API}/platform/jobs/failures/{failure}/rerun", json={"reason": "Try again please"}
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "NOT_RERUNNABLE"
    assert (await admin.get(f"{API}/platform/jobs/queue")).json() == {"waiting": 0}


async def test_an_unknown_failure_is_not_found_and_a_company_admin_cannot_rerun(
    rig: dict[str, Any],
) -> None:
    company_admin = await rig["person"]("company_admin", rig["a"])
    failure = await _seed_failure(rig, "rtw_status_daily")
    assert (
        await company_admin.post(
            f"{API}/platform/jobs/failures/{failure}/rerun", json={"reason": "Not mine"}
        )
    ).status_code == 403
    admin = await _platform_admin(rig, "support")
    missing = await admin.post(
        f"{API}/platform/jobs/failures/{uuid.uuid4()}/rerun", json={"reason": "No such run"}
    )
    assert missing.status_code == 404


def test_only_allow_listed_jobs_have_a_rerun_function() -> None:
    names = {function.name for function in functions()}
    assert "rerun_rtw_status_daily" in names
    assert "rerun_reminders_daily" not in names
    listed = {name.removeprefix("rerun_") for name in names if name.startswith("rerun_")}
    assert listed == RERUNNABLE
