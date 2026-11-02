"""T4.4: the 18 compliance documents: one current per type, replaced on upload, expiry status, access."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
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
from app.modules.companies.compliance_documents import status_of
from app.modules.companies.reference import COMPLIANCE_DOCUMENT_TYPES
from tests.db.api_support import sign_in_as, two_companies
from tests.db.support import DatabaseUnderTest, engine_for
from tests.support import TEST_REDIS_URL, build_settings

S3 = os.environ.get("TEST_S3_ENDPOINT", "http://localhost:9000")
S3_USER = os.environ.get("RUSTFS_ACCESS_KEY", "rustfsadmin")
S3_PASSWORD = os.environ.get("RUSTFS_SECRET_KEY", "rustfsadmin")


TODAY = datetime.now(UTC).date()


def pdf(tag: str) -> bytes:
    return f"%PDF-1.4\n% {tag}\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n".encode()


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
        yield {"person": person, "a": a, "b": b, "db": database}
    for client in clients:
        await client.aclose()
    await redis.flushdb()
    await redis.aclose()


def upload(client: httpx.AsyncClient, doc_type: str, tag: str, **fields: str) -> Any:
    return client.post(
        "/api/v1/compliance-documents",
        files={"file": (f"{tag}.pdf", pdf(tag), "application/pdf")},
        data={"doc_type": doc_type, **fields},
    )


def test_status_follows_the_expiry_date() -> None:
    today = date(2026, 11, 2)
    assert status_of(None, today) == "current"
    assert status_of(today + timedelta(days=61), today) == "current"
    assert status_of(today + timedelta(days=60), today) == "expiring"
    assert status_of(today, today) == "expiring"
    assert status_of(today - timedelta(days=1), today) == "expired"


async def test_all_18_are_listed_and_a_new_upload_replaces_the_old_one(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    empty = (await admin.get("/api/v1/compliance-documents")).json()
    assert (empty["filled"], empty["total"], len(empty["slots"])) == (0, 18, 18)
    assert [s["doc_type"] for s in empty["slots"]] == list(COMPLIANCE_DOCUMENT_TYPES)
    assert {s["status"] for s in empty["slots"]} == {"missing"}

    soon = (TODAY + timedelta(days=20)).isoformat()
    first = await upload(admin, "employers_liability_insurance", "policy-2025", expires_on=soon)
    assert first.status_code == 201, first.text
    assert first.json()["status"] == "expiring"
    second = await upload(
        admin,
        "employers_liability_insurance",
        "policy-2026",
        expires_on=(TODAY + timedelta(days=300)).isoformat(),
        notes="Renewed",
    )
    assert second.json()["status"] == "current"
    listed = (await admin.get("/api/v1/compliance-documents")).json()
    assert listed["filled"] == 1  # replaced, not added to
    held = next(s for s in listed["slots"] if s["doc_type"] == "employers_liability_insurance")
    assert held["record"]["file_name"] == "policy-2026.pdf"
    assert held["record"]["notes"] == "Renewed"
    assert (await admin.get("/api/v1/company")).json()["compliance_documents"] == 1

    link = (await admin.get(f"/api/v1/compliance-documents/{second.json()['id']}/file")).json()
    async with httpx.AsyncClient() as plain:
        assert (await plain.get(link["url"])).content == pdf("policy-2026")


async def test_expiry_and_notes_can_change_and_a_document_can_be_removed(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    made = (await upload(admin, "vat_certificate", "vat")).json()
    assert made["expires_on"] is None
    past = (TODAY - timedelta(days=3)).isoformat()
    patched = await admin.patch(
        f"/api/v1/compliance-documents/{made['id']}", json={"expires_on": past}
    )
    assert patched.json()["status"] == "expired"
    cleared = await admin.patch(
        f"/api/v1/compliance-documents/{made['id']}", json={"expires_on": None}
    )
    assert cleared.json()["status"] == "current"
    assert (await admin.delete(f"/api/v1/compliance-documents/{made['id']}")).status_code == 204
    assert (await admin.get("/api/v1/compliance-documents")).json()["filled"] == 0
    assert (
        await admin.patch(f"/api/v1/compliance-documents/{made['id']}", json={})
    ).status_code == 404


async def test_refusals_roles_and_other_companies(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    assert (await upload(admin, "not_a_type", "x")).status_code == 422
    exe = await admin.post(
        "/api/v1/compliance-documents",
        files={"file": ("scan.pdf", b"MZ\x90\x00" + os.urandom(32), "application/pdf")},
        data={"doc_type": "latest_rti"},
    )
    assert exe.status_code == 415

    made = (await upload(admin, "latest_rti", "rti")).json()
    # An HR Admin maintains the documents; a People Manager may only see the list, not the file.
    hr = await rig["person"]("hr_admin", rig["a"])
    assert (await upload(hr, "other", "hr")).status_code == 201
    manager = await rig["person"]("people_manager", rig["a"])
    assert (await manager.get("/api/v1/compliance-documents")).status_code == 403
    staff = await rig["person"]("employee", rig["a"])
    assert (await staff.get("/api/v1/compliance-documents")).status_code == 403
    assert (await upload(staff, "other", "nope")).status_code == 403

    other = await rig["person"]("company_admin", rig["b"])
    assert (await other.get("/api/v1/compliance-documents")).json()["filled"] == 0
    assert (await other.delete(f"/api/v1/compliance-documents/{made['id']}")).status_code == 404
    assert (await other.get(f"/api/v1/compliance-documents/{made['id']}/file")).status_code == 404

    owner = engine_for(rig["db"].owner_url, poolclass=NullPool)
    async with owner.connect() as c:
        rows = await c.execute(
            text(
                "select action from audit_events where company_id = :c "
                "and action like 'compliance_document%' order by created_at"
            ),
            {"c": rig["a"]},
        )
        assert [r[0] for r in rows] == [
            "compliance_document.added",
            "compliance_document.added",
        ]
    await owner.dispose()
