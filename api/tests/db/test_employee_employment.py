"""T6.5: employment history, validation, audit, RBAC and tenant isolation."""

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


ROLE = {"employment_type": "full_time", "effective_from": "2025-01-06"}


async def test_roles_hire_date_history_and_audit(rig: dict[str, Any]) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    base = f"{API}/employees/{emp}"
    assert (await hr.get(f"{base}/employment")).json()["assignments"] == []
    made = await hr.post(f"{base}/assignments", json=ROLE)
    assert made.status_code == 201, made.text
    assert (await hr.post(f"{base}/assignments", json=ROLE)).status_code == 409
    assert (
        await hr.post(f"{base}/assignments", json={**ROLE, "effective_from": "2024-01-01"})
    ).status_code == 409
    future = {**ROLE, "effective_from": "2099-01-01", "employment_type": "part_time"}
    assert (await hr.post(f"{base}/assignments", json=future)).status_code == 201
    tab = (await hr.get(f"{base}/employment")).json()
    assert len(tab["assignments"]) == 2
    assert tab["assignments"][1]["ended_at"] == "2099-01-01"
    assert (
        await hr.put(f"{base}/hire-date", json={"hire_date": "2025-02-01", "reason": "Correction"})
    ).status_code == 409
    assert (
        await hr.put(f"{base}/hire-date", json={"hire_date": "2025-01-01", "reason": " "})
    ).status_code == 422
    assert (
        await hr.put(
            f"{base}/hire-date", json={"hire_date": "2025-01-01", "reason": "Contract corrected"}
        )
    ).status_code == 204
    assert (await hr.get(f"{base}/employment")).json()["hire_date"] == "2025-01-01"
    async with rig["owner"].connect() as c:
        events = (
            (
                await c.execute(
                    text("select action from audit_events where entity_id = :i"), {"i": emp}
                )
            )
            .scalars()
            .all()
        )
    assert events.count("employee.role_changed") == 2
    assert "employee.hire_date_changed" in events


async def test_records_validate_save_edit_delete_and_isolate(rig: dict[str, Any]) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    other = await _employee(rig, rig["a"], "E2")
    foreign = await _employee(rig, rig["b"], "E1")
    me = await rig["person"]("employee", rig["a"])
    base = f"{API}/employees/{emp}"
    routes = [
        ("responsibilities", {"text": "Support customers"}, {"text": "Lead support"}),
        ("education", {"qualification": "BSc"}, {"qualification": "MSc"}),
        ("training", {"title": "First aid"}, {"title": "Refresher"}),
        ("memberships", {"licence_title": "Member"}, {"licence_title": "Fellow"}),
    ]
    for route, body, edited in routes:
        made = await hr.post(f"{base}/{route}", json=body)
        assert made.status_code == 201, made.text
        rid = made.json()["id"]
        assert (
            await hr.put(f"{API}/employees/{other}/{route}/{rid}", json=edited)
        ).status_code == 404
        assert (await hr.put(f"{base}/{route}/{rid}", json=edited)).status_code == 200
        assert (await hr.get(f"{base}/employment")).json()[route][0].items() >= edited.items()
        assert (await me.post(f"{base}/{route}", json=body)).status_code == 403
        assert (await me.put(f"{base}/{route}/{rid}", json=edited)).status_code == 403
        assert (await me.delete(f"{base}/{route}/{rid}")).status_code == 403
        assert (await hr.post(f"{API}/employees/{foreign}/{route}", json=body)).status_code == 404
        assert (
            await hr.put(f"{API}/employees/{foreign}/{route}/{rid}", json=body)
        ).status_code == 404
        assert (await hr.delete(f"{API}/employees/{foreign}/{route}/{rid}")).status_code == 404
        assert (await hr.delete(f"{base}/{route}/{rid}")).status_code == 204
        assert (await hr.delete(f"{base}/{route}/{rid}")).status_code == 404
    prev = {"job_title": "Adviser", "started_on": "2020-01-01", "left_on": "2024-12-31"}
    assert (await hr.put(f"{base}/previous-employment", json=prev)).status_code == 200
    assert (
        await hr.put(f"{base}/previous-employment", json={**prev, "left_on": "2019-01-01"})
    ).status_code == 422
    assert (
        await hr.post(
            f"{base}/training",
            json={"title": "Aid", "started_on": "2025-02-01", "ended_on": "2025-01-01"},
        )
    ).status_code == 422
    assert (
        await hr.post(f"{base}/education", json={"qualification": "BSc", "percentage": 101})
    ).status_code == 422
    assert (await me.get(f"{base}/employment")).status_code == 404
    assert (await hr.get(f"{API}/employees/{foreign}/employment")).status_code == 404
    for route, body in [
        ("hire-date", {"hire_date": "2025-01-01", "reason": "Fix"}),
        ("previous-employment", prev),
    ]:
        assert (await me.put(f"{base}/{route}", json=body)).status_code == 403
        assert (await hr.put(f"{API}/employees/{foreign}/{route}", json=body)).status_code == 404
    assert (await me.post(f"{base}/assignments", json=ROLE)).status_code == 403
    assert (await hr.post(f"{API}/employees/{foreign}/assignments", json=ROLE)).status_code == 404


async def test_role_links_cannot_cross_tenants_or_create_reporting_loops(
    rig: dict[str, Any],
) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    boss = await _employee(rig, rig["a"], "E2")
    foreign = await _employee(rig, rig["b"], "E1")
    base = f"{API}/employees/{emp}/assignments"
    for field in ("reporting_authority_employee_id", "leave_sanctioning_employee_id"):
        assert (await hr.post(base, json={**ROLE, field: str(foreign)})).status_code == 404
        assert (await hr.post(base, json={**ROLE, field: str(emp)})).status_code == 409
    first = await hr.post(base, json={**ROLE, "reporting_authority_employee_id": str(boss)})
    assert first.status_code == 201, first.text
    loop = await hr.post(
        f"{API}/employees/{boss}/assignments",
        json={**ROLE, "reporting_authority_employee_id": str(emp)},
    )
    assert loop.status_code == 409
    for field in ("department_id", "designation_id", "location_id"):
        assert (
            await hr.post(
                f"{API}/employees/{boss}/assignments", json={**ROLE, field: str(uuid.uuid4())}
            )
        ).status_code == 404
    assert (
        await hr.post(base, json={**ROLE, "custom_working_days": ["mon", "mon"]})
    ).status_code == 422
