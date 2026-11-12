"""Register status and safe manual import operations (T20.5)."""

from __future__ import annotations

from typing import Any

from arq.jobs import Job
from sqlalchemy import text

from tests.db.test_employee_documents import rig as rig
from tests.db.test_platform_jobs import API, _platform_admin, _seed_failure


async def test_register_operations_require_platform_access(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    assert (await admin.get(f"{API}/platform/register/status")).status_code == 403
    assert (
        await admin.post(f"{API}/platform/register/run", json={"reason": "Refresh register"})
    ).status_code == 403


async def test_register_status_empty_then_publication_counts_and_ingest_errors(
    rig: dict[str, Any],
) -> None:
    admin = await _platform_admin(rig, "support")
    empty = await admin.get(f"{API}/platform/register/status")
    assert empty.status_code == 200, empty.text
    assert empty.json() == {
        "last_publication": None,
        "current_sponsors": 0,
        "total_sponsors": 0,
        "errors": [],
    }
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "insert into register_publications "
                "(id, published_on, source_url, row_count, sha256, status) values "
                "(gen_random_uuid(), '2026-11-12', 'https://www.gov.uk/register.csv', 7, "
                "repeat('a', 64), 'complete')"
            )
        )
        await c.execute(
            text(
                "insert into register_sponsors (id, stable_id, organisation_name, normalised_name, "
                "town, county, first_seen_on, last_seen_on, current, place_precision) values "
                "(gen_random_uuid(), 'current', 'Current', 'current', '', '', current_date, "
                "current_date, true, 'none'), "
                "(gen_random_uuid(), 'old', 'Old', 'old', '', '', current_date, "
                "current_date, false, 'none')"
            )
        )
    failure = await _seed_failure(rig, "register_ingest")
    await _seed_failure(rig, "reminders_daily")
    out = (await admin.get(f"{API}/platform/register/status")).json()
    assert out["last_publication"]["published_on"] == "2026-11-12"
    assert out["last_publication"]["row_count"] == 7
    assert out["last_publication"]["status"] == "complete"
    assert out["current_sponsors"] == 1
    assert out["total_sponsors"] == 2
    assert [row["id"] for row in out["errors"]] == [str(failure)]
    assert out["errors"][0]["detail"]["kind"] == "TimeoutError"


async def test_register_rerun_requires_reason_queues_allow_listed_job_and_audits(
    rig: dict[str, Any],
) -> None:
    admin = await _platform_admin(rig, "support")
    for body in ({}, {"reason": " "}, {"reason": "x" * 501}):
        assert (await admin.post(f"{API}/platform/register/run", json=body)).status_code == 422
    assert (await admin.get(f"{API}/platform/jobs/queue")).json() == {"waiting": 0}
    response = await admin.post(
        f"{API}/platform/register/run", json={"reason": "Refresh after source outage"}
    )
    assert response.status_code == 202, response.text
    made = response.json()
    assert made["job"] == "register_ingest"
    info = await Job(made["job_id"], rig["app"].state.auth.redis).info()
    assert info is not None
    assert info.function == "rerun_register_ingest"
    assert info.args == ()
    async with rig["owner"].connect() as c:
        event = (
            await c.execute(
                text(
                    "select reason, after, actor_type from audit_events "
                    "where action='platform.register_rerun'"
                )
            )
        ).one()
    assert event.reason == "Refresh after source outage"
    assert event.after == made
    assert event.actor_type == "platform_admin"
