"""T6.8: employee Activity pagination, permissions and tenant isolation."""

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


async def test_activity_is_real_paginated_and_isolated(rig: dict[str, Any]) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    other = await _employee(rig, rig["a"], "E2")
    foreign = await _employee(rig, rig["b"], "E1")
    base = f"{API}/employees/{emp}"
    assert (await hr.get(f"{base}/activity")).json() == {"items": [], "next_cursor": None}
    for target, name in (
        (emp, "First responsibility"),
        (emp, "Second responsibility"),
        (other, "Other employee"),
    ):
        saved = await hr.post(f"{API}/employees/{target}/responsibilities", json={"text": name})
        assert saved.status_code == 201
    first = await hr.get(f"{base}/activity", params={"limit": 1})
    assert first.status_code == 200, first.text
    data = first.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["action"] == "employee.responsibility_added"
    assert data["items"][0]["after"]["text"] == "Second responsibility"
    assert data["next_cursor"]
    second = (
        await hr.get(f"{base}/activity", params={"limit": 1, "cursor": data["next_cursor"]})
    ).json()
    assert second["items"][0]["after"]["text"] == "First responsibility"
    assert second["next_cursor"] is None
    assert (await hr.get(f"{base}/activity", params={"cursor": "invalid"})).status_code == 422
    assert (await hr.get(f"{API}/employees/{foreign}/activity")).status_code == 404
    for role in ("employee", "people_manager", "recruiter"):
        person = await rig["person"](role, rig["a"])
        assert (await person.get(f"{base}/activity")).status_code == 403
    auditor = await rig["person"]("read_only_auditor", rig["a"])
    assert (await auditor.get(f"{base}/activity")).status_code == 200
