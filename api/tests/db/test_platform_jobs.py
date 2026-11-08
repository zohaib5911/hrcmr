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

from tests.db.test_employee_documents import rig as rig
from tests.support import TEST_REDIS_URL

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
