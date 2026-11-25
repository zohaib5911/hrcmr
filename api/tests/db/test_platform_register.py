"""Register status and safe manual import operations (T20.5)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from arq import create_pool
from arq.jobs import Job
from sqlalchemy import text

from app.jobs.queue import redis_settings
from tests.db.test_employee_documents import rig as rig
from tests.db.test_platform_jobs import API, _platform_admin, _seed_failure


@pytest.fixture(autouse=True)
async def clean_register(rig: dict[str, Any]) -> AsyncIterator[None]:
    async with rig["owner"].begin() as c:
        await c.execute(text("truncate register_publications, register_sponsors cascade"))
    yield
    async with rig["owner"].begin() as c:
        await c.execute(text("truncate register_publications, register_sponsors cascade"))


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
        "held_import": None,
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
    pool = await create_pool(redis_settings(rig["app"].state.settings))
    try:
        info = await Job(made["job_id"], pool).info()
    finally:
        await pool.aclose()
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


async def test_a_held_import_is_shown_and_approving_it_queues_the_import(
    rig: dict[str, Any],
) -> None:
    """ISS-11: the operator reviews a held import and approves it for the next run."""
    admin = await _platform_admin(rig, "support")
    async with rig["owner"].begin() as c:
        held = (
            await c.execute(
                text(
                    "insert into register_publications "
                    "(id, published_on, source_url, row_count, sha256, status) values "
                    "(gen_random_uuid(), '2026-11-13', 'https://www.gov.uk/register.csv', 1, "
                    "repeat('b', 64), 'held') returning id"
                )
            )
        ).scalar_one()
    status = (await admin.get(f"{API}/platform/register/status")).json()
    assert status["held_import"]["id"] == str(held)
    assert status["held_import"]["status"] == "held"
    url = f"{API}/platform/register/holds/{held}/approve"
    assert (await admin.post(url, json={})).status_code == 422
    approved = await admin.post(url, json={"reason": "Home Office confirmed the reduction"})
    assert approved.status_code == 202, approved.text
    assert approved.json()["job"] == "register_ingest"
    again = await admin.post(url, json={"reason": "Twice"})
    assert again.status_code == 404  # no longer held
    async with rig["owner"].connect() as c:
        state = (
            await c.execute(
                text("select status from register_publications where id = :i"), {"i": held}
            )
        ).scalar_one()
        audited = (
            await c.execute(
                text(
                    "select count(*) from audit_events "
                    "where action = 'platform.register_hold_approved' and entity_id = :i"
                ),
                {"i": held},
            )
        ).scalar_one()
    assert state == "approved"
    assert audited == 1
