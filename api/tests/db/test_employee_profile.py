"""T6.3: the employee profile (header and Overview), lifecycle status, the 48-hour opt-out with its
signed agreement, and the guarded permanent delete."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
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
S3 = os.environ.get("TEST_S3_ENDPOINT", "http://localhost:9000")
S3_USER = os.environ.get("RUSTFS_ACCESS_KEY", "rustfsadmin")
S3_PASSWORD = os.environ.get("RUSTFS_SECRET_KEY", "rustfsadmin")
PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
TODAY = datetime.now(UTC).date().isoformat()


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
    app = create_app(
        build_settings(
            database_url=database.app_url,
            redis_url=TEST_REDIS_URL,
            r2_endpoint=S3,
            r2_access_key_id=S3_USER,
            r2_secret_access_key=S3_PASSWORD,
            r2_bucket_files="files-dev",
        )
    )
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


async def _new(client: httpx.AsyncClient, number: str = "E001") -> dict[str, Any]:
    made = await client.post(
        f"{API}/employees",
        json={
            "first_name": "Tom",
            "last_name": "Baker",
            "email": "tom@example.com",
            "employee_number": number,
            "hire_date": TODAY,
        },
    )
    assert made.status_code == 201, made.text
    created: dict[str, Any] = made.json()
    return created


async def test_the_profile_header_and_who_may_open_it(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    tom = await _new(admin)
    profile = (await admin.get(f"{API}/employees/{tom['id']}")).json()
    assert (profile["first_name"], profile["status"], profile["documents"]) == ("Tom", "active", 0)
    assert profile["opted_out_48h_week"] is False
    assert profile["can_delete"] is True

    other = await rig["person"]("company_admin", rig["b"])
    assert (await other.get(f"{API}/employees/{tom['id']}")).status_code == 404
    # An employee who is not this person does not reach the record.
    staff = await rig["person"]("employee", rig["a"])
    assert (await staff.get(f"{API}/employees/{tom['id']}")).status_code == 404
    assert (await admin.get(f"{API}/employees/{uuid.uuid4()}")).status_code == 404


async def test_lifecycle_changes_are_recorded_and_need_the_write_permission(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    tom = await _new(admin)
    url = f"{API}/employees/{tom['id']}/status"
    left = await admin.post(url, json={"status": "leaver", "leave_date": "2026-12-31"})
    assert left.json()["status"] == "leaver"
    assert left.json()["leave_date"] == "2026-12-31"
    back = await admin.post(url, json={"status": "active"})
    assert (back.json()["status"], back.json()["leave_date"]) == ("active", None)
    assert (await admin.post(url, json={"status": "archived"})).json()["status"] == "archived"
    assert (await admin.post(url, json={"status": "nonsense"})).status_code == 422

    manager = await rig["person"]("people_manager", rig["a"])
    assert (await manager.post(url, json={"status": "active"})).status_code == 403
    async with rig["owner"].connect() as c:
        actions = [
            r[0]
            for r in await c.execute(
                text(
                    "select action from audit_events where entity_id = :i "
                    "and action like 'employee.status%' order by created_at"
                ),
                {"i": uuid.UUID(tom["id"])},
            )
        ]
    assert actions == ["employee.status_changed"] * 3


async def test_the_48_hour_opt_out_needs_the_signed_agreement(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    tom = await _new(admin)
    base = f"{API}/employees/{tom['id']}/opt-out-48h"
    refused = await admin.put(base, json={"opted_out": True})
    assert refused.status_code == 409
    assert refused.json()["error"]["field"] == "opted_out"

    sent = await admin.post(
        f"{base}/agreement", files={"file": ("opt-out.pdf", PDF, "application/pdf")}
    )
    assert sent.status_code == 204, sent.text
    profile = (await admin.get(f"{API}/employees/{tom['id']}")).json()
    assert (profile["has_opt_out_agreement"], profile["documents"]) == (True, 1)
    on = await admin.put(base, json={"opted_out": True})
    assert on.json()["opted_out_48h_week"] is True
    off = await admin.put(base, json={"opted_out": False})
    assert off.json()["opted_out_48h_week"] is False


async def test_permanent_delete_only_for_a_clean_record_and_a_typed_name(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    mistake = await _new(admin, "E100")
    url = f"{API}/employees/{mistake['id']}"
    wrong = await admin.request("DELETE", url, json={"confirm_name": "Tim Baker"})
    assert wrong.status_code == 422
    assert wrong.json()["error"]["field"] == "confirm_name"

    hr = await rig["person"]("hr_admin", rig["a"])
    # HR Admins may delete too (plan 8.3), and a deleted record is gone.
    assert (await hr.request("DELETE", url, json={"confirm_name": "tom baker"})).status_code == 204
    assert (await admin.get(url)).status_code == 404

    # A record with history cannot be deleted: it is archived instead.
    kept = await _new(admin, "E101")
    await admin.post(f"{API}/employees/{kept['id']}/status", json={"status": "leaver"})
    profile = (await admin.get(f"{API}/employees/{kept['id']}")).json()
    assert profile["can_delete"] is False
    assert "Archive it instead" in profile["delete_blocker"]
    blocked = await admin.request(
        "DELETE", f"{API}/employees/{kept['id']}", json={"confirm_name": "Tom Baker"}
    )
    assert blocked.status_code == 409

    manager = await rig["person"]("people_manager", rig["a"])
    assert (
        await manager.request("DELETE", url, json={"confirm_name": "Tom Baker"})
    ).status_code == 403
