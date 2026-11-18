"""T22.2: performance budgets. With 1,000 seeded employees the main lists answer in under 300 ms at
p95 (in-process, so this is the API and database time without the network), and their main
queries use an index rather than reading the whole table."""

from __future__ import annotations

import gc
import os
import statistics
import time
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from app.core.crypto import KeyRing, set_keyring
from app.main import create_app
from app.modules.auth.sessions import SessionStore
from seed.perf import seed_company
from tests.db.api_support import sign_in_as, two_companies
from tests.db.support import DatabaseUnderTest, engine_for
from tests.support import TEST_REDIS_URL, build_settings

API = "/api/v1"
BUDGET_MS = 300
RUNS = 40


@pytest.fixture(autouse=True)
def _keys() -> Iterator[None]:
    set_keyring(KeyRing(keys={"k1": os.urandom(32)}, active_kid="k1", blind_key=os.urandom(32)))
    yield
    set_keyring(None)


@pytest.fixture
async def rig(database: DatabaseUnderTest) -> AsyncIterator[dict[str, Any]]:
    redis = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    await redis.flushdb()
    a, b = await two_companies(database)
    owner = engine_for(database.owner_url, poolclass=NullPool)
    async with owner.begin() as c:
        await seed_company(c, a)
        await seed_company(c, b, count=200)  # another company's rows must not slow company a
    app = create_app(build_settings(database_url=database.app_url, redis_url=TEST_REDIS_URL))
    async with LifespanManager(app):
        admin = await sign_in_as(database, SessionStore(redis), app, "company_admin", a)
        gc.collect()
        gc.freeze()  # as gunicorn.conf.py post_worker_init does in production
        try:
            yield {"admin": admin, "a": a, "owner": owner}
        finally:
            gc.unfreeze()
            await admin.aclose()
    await owner.dispose()
    await redis.flushdb()
    await redis.aclose()


def _lists() -> list[str]:
    today = datetime.now(UTC).date()
    month = f"start={today - timedelta(days=30)}&end={today}"
    return [
        "/employees",
        "/employees?q=perf0042",
        "/employees?status=active&rtw=NeedsAttention",
        "/employees/summary",
        "/dashboard",
        "/leave/requests",
        "/leave/requests?status=pending",
        "/leave-balances",
        f"/attendance-records?{month}",
        "/compliance/overview",
    ]


async def _p95(client: httpx.AsyncClient, path: str) -> float:
    for _ in range(2):  # warm-up: first-call imports and connection set-up are not the budget
        assert (await client.get(API + path)).status_code == 200, path
    timings = []
    for _ in range(RUNS):
        started = time.perf_counter()
        response = await client.get(API + path)
        timings.append((time.perf_counter() - started) * 1000)
        assert response.status_code == 200, path
    return statistics.quantiles(timings, n=20)[-1]


async def test_seed_makes_a_thousand_people(rig: dict[str, Any]) -> None:
    body = (await rig["admin"].get(f"{API}/employees?archived=true")).json()
    assert body["total"] == 1000


async def test_main_lists_meet_the_p95_budget(rig: dict[str, Any]) -> None:
    results = {path: await _p95(rig["admin"], path) for path in _lists()}
    slow = {path: round(ms) for path, ms in results.items() if ms >= BUDGET_MS}
    print({path: round(ms) for path, ms in results.items()})  # noqa: T201 (visible with -s)
    assert not slow, f"p95 over {BUDGET_MS} ms: {slow}"


async def _plan(rig: dict[str, Any], sql: str, params: dict[str, Any]) -> str:
    """The plan Postgres picks with sequential scans discouraged: if an index can serve the query,
    the plan shows it. A table this small would otherwise be scanned whatever the indexes."""
    async with rig["owner"].begin() as c:
        await c.execute(text("set local enable_seqscan = off"))
        rows = (await c.execute(text(f"explain {sql}"), params)).scalars().all()
    return "\n".join(rows)


EXPLAINED = {
    "employee list (active, by name)": (
        "select id from employees where company_id = :c and status <> 'archived' "
        "order by lower(last_name), lower(first_name) limit 200",
        "ix_employees_company_id_name",
    ),
    "current assignment of a person": (
        "select department_id from employee_assignments where employee_id = :e "
        "and effective_from <= current_date and (ended_at is null or ended_at > current_date)",
        "employee_assignments_employee_id",
    ),
    "leave requests, newest first": (
        "select id from leave_requests where company_id = :c "
        "order by start_date desc, id desc limit 200",
        "ix_leave_requests_company_id_start_date",
    ),
    "pending leave requests": (
        "select id from leave_requests where company_id = :c and status = 'pending' "
        "order by start_date desc, id desc limit 200",
        "ix_leave_requests_company_id_start_date",
    ),
    # O6.1.3: search anywhere in a name, as the queries write it (lower(x) LIKE '%text%').
    "public sponsor search by name": (
        "select id from register_sponsors where organisation_name ilike '%' || 'care' || '%'",
        "ix_register_sponsors_name_trgm",
    ),
    "public sponsor search by town": (
        "select id from register_sponsors where town ilike '%' || 'leed' || '%'",
        "ix_register_sponsors_town_trgm",
    ),
    "people search by full name": (
        "select id from employees where lower(first_name || ' ' || last_name) like '%ira ha%'",
        "ix_employees_full_name_trgm",
    ),
    "candidate search by full name": (
        "select id from candidates where lower(first_name || ' ' || last_name) like '%ira ha%'",
        "ix_candidates_full_name_trgm",
    ),
    "attendance for a month": (
        "select id from attendance_records where company_id = :c "
        "and date between current_date - 30 and current_date order by date desc limit 50",
        "ix_attendance_records_company_id_date",
    ),
}


@pytest.mark.parametrize("name", EXPLAINED)
async def test_main_queries_use_an_index(rig: dict[str, Any], name: str) -> None:
    sql, index = EXPLAINED[name]
    async with rig["owner"].connect() as c:
        employee = (
            await c.execute(
                text("select id from employees where company_id = :c limit 1"), {"c": rig["a"]}
            )
        ).scalar_one()
    plan = await _plan(rig, sql, {"c": rig["a"], "e": employee})
    assert index in plan, plan
    assert "Seq Scan" not in plan, plan
