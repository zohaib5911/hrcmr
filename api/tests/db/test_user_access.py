"""T5.1: the User Access list: who may read it, the role and status filters, search, the unlinked
count, and that another company's people never appear."""

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
        yield {"person": person, "a": a, "b": b, "owner": owner}
    for client in clients:
        await client.aclose()
    await owner.dispose()
    await redis.flushdb()
    await redis.aclose()


async def test_the_list_filters_and_counts_unlinked_users(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    await rig["person"]("hr_admin", rig["a"])
    await rig["person"]("employee", rig["a"])
    await rig["person"]("company_admin", rig["b"])  # another company: never listed

    everyone = (await admin.get(f"{API}/users")).json()
    assert everyone["total"] == 3
    assert everyone["unlinked"] == 3  # no employee records exist yet
    assert sorted(u["role"] for u in everyone["users"]) == ["company_admin", "employee", "hr_admin"]
    assert [u["is_you"] for u in everyone["users"]].count(True) == 1
    first = everyone["users"][0]
    assert set(first) >= {"two_step", "employee_id", "status", "email", "last_login_at"}
    assert "password_hash" not in str(everyone)
    assert "mfa_secret" not in str(everyone)

    only_hr = (await admin.get(f"{API}/users", params={"role": "hr_admin"})).json()
    assert [u["role"] for u in only_hr["users"]] == ["hr_admin"]
    assert only_hr["total"] == 3  # the counts ignore the filters

    async with rig["owner"].begin() as c:
        await c.execute(text("update memberships set status = 'suspended' where role = 'employee'"))
        await c.execute(
            text("update memberships set employee_id = :e where role = 'hr_admin'"),
            {"e": uuid.uuid4()},
        )
    suspended = (await admin.get(f"{API}/users", params={"status": "suspended"})).json()
    assert [u["role"] for u in suspended["users"]] == ["employee"]
    after = (await admin.get(f"{API}/users")).json()
    assert after["unlinked"] == 1  # only the admin: the HR admin is linked, the employee suspended

    found = (await admin.get(f"{API}/users", params={"q": "hr_admin"})).json()
    assert [u["role"] for u in found["users"]] == ["hr_admin"]
    assert (await admin.get(f"{API}/users", params={"q": "%"})).json()["users"] == []
    assert (await admin.get(f"{API}/users", params={"role": "boss"})).status_code == 422


async def test_only_the_roles_that_hold_the_permission_may_read_the_list(
    rig: dict[str, Any],
) -> None:
    for role, allowed in (
        ("company_admin", True),
        ("hr_admin", True),
        ("read_only_auditor", True),
        ("people_manager", False),
        ("recruiter", False),
        ("employee", False),
    ):
        person = await rig["person"](role, rig["a"])
        assert (await person.get(f"{API}/users")).status_code == (200 if allowed else 403), role
    assert (
        await (await rig["person"]("employee", rig["a"])).get(f"{API}/users")
    ).status_code == 403
