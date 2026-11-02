"""T6.6: permission-gated salary history, references and minimum wage preview."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Iterator
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
from tests.db.api_support import sign_in_as, two_companies
from tests.db.support import DatabaseUnderTest, engine_for
from tests.support import TEST_REDIS_URL, build_settings

API = "/api/v1"


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
    app = create_app(build_settings(database_url=database.app_url, redis_url=TEST_REDIS_URL))
    sessions = SessionStore(redis)
    clients: list[httpx.AsyncClient] = []

    async def person(role: str, company: uuid.UUID) -> httpx.AsyncClient:
        client = await sign_in_as(database, sessions, app, role, company)
        clients.append(client)
        return client

    async with LifespanManager(app):
        yield {"person": person, "a": a, "b": b, "owner": owner, "app": app, "sessions": sessions}
    for client in clients:
        await client.aclose()
    await owner.dispose()
    await redis.flushdb()
    await redis.aclose()


async def _employee(rig: dict[str, Any], company: uuid.UUID, number: str) -> uuid.UUID:
    ident = uuid.uuid4()
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "insert into employees (id, company_id, employee_number, first_name, last_name, "
                "email, hire_date) values (:i, :c, :n, 'Amira', 'Hassan', 'a@example.com', "
                "'2025-01-06')"
            ),
            {"i": ident, "c": company, "n": number},
        )
    return ident


SALARY = {
    "amount": "26000.00",
    "frequency": "annual",
    "contracted_hours_per_week": "40",
    "effective_from": "2026-04-01",
}


async def test_salary_history_checks_and_permissions(rig: dict[str, Any]) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    foreign = await _employee(rig, rig["b"], "E1")
    base = f"{API}/employees/{emp}/compensation"
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update employees set date_of_birth = '1990-01-01' where id = :i"), {"i": emp}
        )
    assert (await hr.get(base)).json() == {"current": None, "records": []}
    check = await hr.post(f"{base}/check", json=SALARY)
    assert check.status_code == 200, check.text
    assert check.json()["below_minimum"] is True
    assert check.json()["minimum_rate"] == "12.71"
    made = await hr.post(base, json=SALARY)
    assert made.status_code == 201, made.text
    assert (await hr.post(base, json=SALARY)).status_code == 409
    future = {**SALARY, "amount": "52000", "effective_from": "2099-01-01"}
    assert (await hr.post(base, json=future)).status_code == 201
    history = (await hr.get(base)).json()
    assert history["current"]["amount"] == "26000.00"
    assert len(history["records"]) == 2
    for bad in ({"amount": -1}, {"contracted_hours_per_week": 0}, {"frequency": "weekly"}):
        assert (await hr.post(base, json={**SALARY, **bad})).status_code == 422
    for route in (base, f"{base}/check"):
        assert (
            await hr.post(route, json={**SALARY, "effective_from": "2024-01-01"})
        ).status_code == 409
    for field in ("tax_code_id", "payment_type_id", "pay_band_id", "pay_schedule_id"):
        assert (
            await hr.post(
                base, json={**SALARY, "effective_from": "2025-01-06", field: str(uuid.uuid4())}
            )
        ).status_code == 404
    for role in ("employee", "people_manager", "recruiter"):
        person = await rig["person"](role, rig["a"])
        assert (await person.get(base)).status_code == 403
        assert (await person.post(base, json=SALARY)).status_code == 403
        assert (await person.post(f"{base}/check", json=SALARY)).status_code == 403
    auditor = await rig["person"]("read_only_auditor", rig["a"])
    assert (await auditor.get(base)).status_code == 200
    assert (await auditor.post(base, json=SALARY)).status_code == 403
    outside = f"{API}/employees/{foreign}/compensation"
    assert (await hr.get(outside)).status_code == 404
    assert (await hr.post(outside, json=SALARY)).status_code == 404
    assert (await hr.post(f"{outside}/check", json=SALARY)).status_code == 404
    async with rig["owner"].connect() as c:
        count = (
            await c.execute(
                text(
                    "select count(*) from audit_events where entity_id = :i and action = 'employee.compensation_added'"
                ),
                {"i": emp},
            )
        ).scalar_one()
    assert count == 2
