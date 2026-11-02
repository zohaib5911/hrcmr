"""T4.3: key personnel (the four roles), "same as the Authorising Officer", proof of identity."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
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

S3 = os.environ.get("TEST_S3_ENDPOINT", "http://localhost:9000")
S3_USER = os.environ.get("RUSTFS_ACCESS_KEY", "rustfsadmin")
S3_PASSWORD = os.environ.get("RUSTFS_SECRET_KEY", "rustfsadmin")
PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"


@pytest.fixture(autouse=True)
def _keys() -> Any:
    set_keyring(KeyRing(keys={"k1": os.urandom(32)}, active_kid="k1", blind_key=os.urandom(32)))
    yield
    set_keyring(None)


@pytest.fixture
async def rig(database: DatabaseUnderTest) -> AsyncIterator[dict[str, Any]]:
    redis = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    await redis.flushdb()
    a, b = await two_companies(database)
    settings = build_settings(
        database_url=database.app_url,
        redis_url=TEST_REDIS_URL,
        r2_endpoint=S3,
        r2_access_key_id=S3_USER,
        r2_secret_access_key=S3_PASSWORD,
        r2_bucket_files="files-dev",
    )
    app = create_app(settings)
    sessions = SessionStore(redis)
    clients: list[httpx.AsyncClient] = []

    async def person(role: str, company: uuid.UUID) -> httpx.AsyncClient:
        client = await sign_in_as(database, sessions, app, role, company)
        clients.append(client)
        return client

    async with LifespanManager(app):
        yield {"person": person, "a": a, "b": b, "db": database}
    for client in clients:
        await client.aclose()
    await redis.flushdb()
    await redis.aclose()


def body(role: str, first: str = "Amira", **more: Any) -> dict[str, Any]:
    return {
        "role": role,
        "first_name": first,
        "last_name": "Hassan",
        "designation": "Director",
        "phone": "+44 20 7946 0000",
        "email": f"{first.lower()}@example.com",
        **more,
    }


async def _actions(database: DatabaseUnderTest, company: uuid.UUID) -> list[str]:
    owner = engine_for(database.owner_url, poolclass=NullPool)
    try:
        async with owner.connect() as c:
            result = await c.execute(
                text(
                    "select action from audit_events where company_id = :c "
                    "and action like 'key_person%' order by created_at"
                ),
                {"c": company},
            )
            return [row[0] for row in result]
    finally:
        await owner.dispose()


async def test_one_person_per_role_except_level_two_and_the_count_of_roles(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    assert (await admin.get("/api/v1/key-personnel")).json() == {"people": [], "roles_filled": 0}
    assert (
        await admin.post("/api/v1/key-personnel", json=body("level1_user", "Tom"))
    ).status_code == 201
    officer = await admin.post("/api/v1/key-personnel", json=body("authorising_officer"))
    assert officer.status_code == 201
    again = await admin.post("/api/v1/key-personnel", json=body("authorising_officer", "Zed"))
    assert again.status_code == 409
    assert "already have a Authorising Officer" in again.json()["error"]["message"]
    for first in ("Una", "Vic"):
        assert (
            await admin.post("/api/v1/key-personnel", json=body("level2_user", first))
        ).status_code == 201
    listed = (await admin.get("/api/v1/key-personnel")).json()
    assert [p["role"] for p in listed["people"]] == [
        "authorising_officer",
        "level1_user",
        "level2_user",
        "level2_user",
    ]
    assert listed["roles_filled"] == 3
    assert (await admin.get("/api/v1/company")).json()["key_personnel_roles"] == 3


async def test_the_same_person_as_the_officer_follows_the_officers_details(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    # Nobody can be "the same as" an officer who is not there yet.
    nobody = await admin.post(
        "/api/v1/key-personnel", json=body("key_contact", "X", same_as_authorising_officer=True)
    )
    assert nobody.status_code == 409
    officer = (await admin.post("/api/v1/key-personnel", json=body("authorising_officer"))).json()
    contact = (
        await admin.post(
            "/api/v1/key-personnel",
            json={
                "role": "key_contact",
                "first_name": "Ignored",
                "last_name": "Ignored",
                "same_as_authorising_officer": True,
            },
        )
    ).json()
    assert (contact["first_name"], contact["email"]) == ("Amira", "amira@example.com")

    await admin.patch(
        f"/api/v1/key-personnel/{officer['id']}",
        json={"designation": "Managing director", "phone": "020 7946 0001"},
    )
    again = (await admin.get("/api/v1/key-personnel")).json()["people"]
    follower = next(p for p in again if p["role"] == "key_contact")
    assert (follower["designation"], follower["phone"]) == ("Managing director", "020 7946 0001")
    # The follower's own edits to those details do not stick.
    edited = await admin.patch(
        f"/api/v1/key-personnel/{follower['id']}", json={"first_name": "Someone else"}
    )
    assert edited.json()["first_name"] == "Amira"
    # The officer cannot be the same as themselves; removing the officer frees the others.
    assert (
        await admin.patch(
            f"/api/v1/key-personnel/{officer['id']}", json={"same_as_authorising_officer": True}
        )
    ).status_code == 422
    assert (await admin.delete(f"/api/v1/key-personnel/{officer['id']}")).status_code == 204
    left = (await admin.get("/api/v1/key-personnel")).json()["people"]
    assert [p["same_as_authorising_officer"] for p in left] == [False]
    assert left[0]["first_name"] == "Amira"


async def test_proof_of_identity_is_scanned_kept_and_shown_only_to_those_who_manage(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    person = (await admin.post("/api/v1/key-personnel", json=body("authorising_officer"))).json()
    url = f"/api/v1/key-personnel/{person['id']}/proof-of-id"
    assert (await admin.get(url)).status_code == 404

    sent = await admin.post(url, files={"file": ("passport.pdf", PDF, "application/pdf")})
    assert sent.status_code == 204, sent.text
    listed = (await admin.get("/api/v1/key-personnel")).json()["people"][0]
    assert listed["has_proof_of_id"] is True
    assert listed["proof_of_id_name"] == "passport.pdf"
    link = (await admin.get(url)).json()
    assert link["expires_in"] == 60
    async with httpx.AsyncClient() as plain:
        assert (await plain.get(link["url"])).content == PDF

    # Only pictures and PDFs, nothing executable named as one.
    refused = await admin.post(
        url, files={"file": ("scan.pdf", b"MZ\x90\x00" + os.urandom(32), "application/pdf")}
    )
    assert refused.status_code == 415

    # An HR Admin can see who the key people are, but not their identity documents or change them.
    hr = await rig["person"]("hr_admin", rig["a"])
    assert (await hr.get("/api/v1/key-personnel")).status_code == 200
    assert (await hr.get(url)).status_code == 403
    assert (
        await hr.post("/api/v1/key-personnel", json=body("key_contact", "Kay"))
    ).status_code == 403
    assert (
        await rig["person"]("employee", rig["a"])
    ).headers  # an employee holds no company profile
    # An employee holds no company profile permission at all.
    staff = await rig["person"]("employee", rig["a"])
    assert (await staff.get("/api/v1/key-personnel")).status_code == 403

    # Another company can neither see the person nor their document.
    other = await rig["person"]("company_admin", rig["b"])
    assert (await other.get("/api/v1/key-personnel")).json()["people"] == []
    assert (await other.get(url)).status_code == 404
    assert (await other.delete(f"/api/v1/key-personnel/{person['id']}")).status_code == 404

    assert (await admin.delete(url)).status_code == 204
    assert (await admin.get(url)).status_code == 404
    assert await _actions(rig["db"], rig["a"]) == [
        "key_person.added",
        "key_person.proof_of_id_added",
        "key_person.proof_of_id_removed",
    ]


async def test_bad_details_are_refused_with_the_field(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    bad = await admin.post("/api/v1/key-personnel", json=body("key_contact", email="not-an-email"))
    assert bad.status_code == 422
    assert bad.json()["error"]["field"] == "email"
    assert (
        await admin.post("/api/v1/key-personnel", json=body("key_contact", phone="call"))
    ).status_code == 422
    assert (await admin.post("/api/v1/key-personnel", json=body("boss"))).status_code == 422
    assert (
        await admin.post("/api/v1/key-personnel", json=body("key_contact", extra=1))
    ).status_code == 422
