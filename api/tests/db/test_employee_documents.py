"""T6.7: scanned employee documents and masked inspection PDF."""

from __future__ import annotations

import io
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from pypdf import PdfReader
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from app.core.crypto import KeyRing, set_keyring
from app.main import create_app
from app.modules.auth.sessions import SessionStore
from tests.db.api_support import sign_in_as, two_companies
from tests.db.support import DatabaseUnderTest, engine_for
from tests.db.test_company import png
from tests.db.test_files import PDF, S3_ACCESS, S3_BUCKET, S3_ENDPOINT, S3_SECRET
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
    app = create_app(
        build_settings(
            database_url=database.app_url,
            redis_url=TEST_REDIS_URL,
            r2_endpoint=S3_ENDPOINT,
            r2_access_key_id=S3_ACCESS,
            r2_secret_access_key=S3_SECRET,
            r2_bucket_files=S3_BUCKET,
        )
    )
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


async def test_documents_upload_scan_download_rbac_and_isolation(rig: dict[str, Any]) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    other = await _employee(rig, rig["a"], "E2")
    foreign = await _employee(rig, rig["b"], "E1")
    base = f"{API}/employees/{emp}/documents"
    assert (await hr.get(base)).json() == []
    made = await hr.post(
        base,
        files={"file": ("contract.pdf", PDF, "application/pdf")},
        data={"category": "employment_contract", "notes": "Signed contract"},
    )
    assert made.status_code == 201, made.text
    doc = made.json()
    assert doc["scan_status"] == "clean"
    assert doc["notes"] == "Signed contract"
    assert len((await hr.get(base)).json()) == 1
    link = await hr.get(f"{base}/{doc['id']}/download")
    assert link.status_code == 200, link.text
    assert link.json()["expires_in"] == 60
    assert "X-Amz-Expires=60" in link.json()["url"]
    for bad in ("bad_category", ""):
        assert (
            await hr.post(base, files={"file": ("a.pdf", PDF)}, data={"category": bad})
        ).status_code == 422
    mismatch = await hr.post(
        base, files={"file": ("a.pdf", b"MZ-not-a-pdf")}, data={"category": "other"}
    )
    assert mismatch.status_code == 415
    assert (
        await hr.get(f"{API}/employees/{other}/documents/{doc['id']}/download")
    ).status_code == 404
    assert (await hr.get(f"{API}/employees/{foreign}/documents")).status_code == 404
    assert (
        await hr.post(
            f"{API}/employees/{foreign}/documents",
            files={"file": ("a.pdf", PDF)},
            data={"category": "other"},
        )
    ).status_code == 404
    assert (
        await hr.get(f"{API}/employees/{foreign}/documents/{doc['id']}/download")
    ).status_code == 404
    me = await rig["person"]("employee", rig["a"])
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update memberships set employee_id=:e where company_id=:c and role='employee'"),
            {"e": emp, "c": rig["a"]},
        )
    assert (await me.get(base)).status_code == 200
    assert (await me.get(f"{base}/{doc['id']}/download")).status_code == 200
    assert (
        await me.post(base, files={"file": ("own.pdf", PDF)}, data={"category": "certificate"})
    ).status_code == 201
    assert (await me.get(f"{API}/employees/{other}/documents")).status_code == 404
    assert (
        await me.post(
            f"{API}/employees/{other}/documents",
            files={"file": ("a.pdf", PDF)},
            data={"category": "other"},
        )
    ).status_code == 404
    assert (
        await me.get(f"{API}/employees/{other}/documents/{doc['id']}/download")
    ).status_code == 404
    manager = await rig["person"]("people_manager", rig["a"])
    assert (await manager.get(base)).status_code == 403
    assert (
        await manager.post(base, files={"file": ("a.pdf", PDF)}, data={"category": "other"})
    ).status_code == 403
    assert (await manager.get(f"{base}/{doc['id']}/download")).status_code == 403
    # A file awaiting a new scan must not be served, even through this employee-specific route.
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update files set scan_status='pending' where id=:i"),
            {"i": uuid.UUID(doc["file_id"])},
        )
    assert (await hr.get(f"{base}/{doc['id']}/download")).status_code == 404
    assert (await hr.get(base)).json()[-1]["scan_status"] == "pending"
    async with rig["owner"].connect() as c:
        actions = set(
            (
                await c.execute(
                    text("select action from audit_events where company_id=:c"), {"c": rig["a"]}
                )
            ).scalars()
        )
    assert {"employee.document_added", "file.uploaded", "file.downloaded"} <= actions


async def test_pdf_is_dated_masked_complete_and_permission_gated(rig: dict[str, Any]) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    foreign = await _employee(rig, rig["b"], "E1")
    base = f"{API}/employees/{emp}"
    assert (
        await hr.put(
            f"{base}/identity", json={"ni_number": "AB123456C", "passport_number": "123456789"}
        )
    ).status_code == 200
    assert (
        await hr.put(
            f"{base}/bank",
            json={
                "account_holder": "Amira Hassan",
                "bank_name": "Example Bank",
                "sort_code": "123456",
                "account_number": "12345678",
            },
        )
    ).status_code == 200
    assert (
        await hr.post(
            f"{base}/compensation",
            json={"amount": "35000", "frequency": "annual", "effective_from": "2025-01-06"},
        )
    ).status_code == 201
    assert (
        await hr.post(
            f"{base}/education", json={"qualification": "BSc", "institution": "Example University"}
        )
    ).status_code == 201
    response = await hr.get(f"{base}/record.pdf")
    assert response.status_code == 200, response.text[:100] if response.status_code != 200 else ""
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.content.startswith(b"%PDF-")
    reader = PdfReader(io.BytesIO(response.content))
    output = "\n".join(page.extract_text() for page in reader.pages)
    assert len(reader.pages) > 1
    for value in (
        "Amira Hassan",
        "Generated",
        "Example Bank",
        "35000",
        "Example University",
        "Education",
        "Documents",
        "Page 1",
    ):
        assert value in output, value
    for secret in ("AB123456C", "AB 12 34 56 C", "123456789", "12345678", "12-34-56"):
        assert secret not in output
    assert (await hr.get(f"{API}/employees/{foreign}/record.pdf")).status_code == 404
    for role in ("employee", "people_manager", "read_only_auditor"):
        person = await rig["person"](role, rig["a"])
        assert (await person.get(f"{base}/record.pdf")).status_code == 403
    async with rig["owner"].connect() as c:
        actions = set(
            (
                await c.execute(
                    text("select action from audit_events where entity_id=:e"), {"e": emp}
                )
            ).scalars()
        )
    assert "employee.record_exported" in actions


async def test_profile_photo_is_scanned_scoped_and_audited(rig: dict[str, Any]) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    other = await _employee(rig, rig["b"], "E1")
    base = f"{API}/employees/{emp}"
    assert (await hr.get(f"{base}/photo")).status_code == 404
    assert (
        await hr.post(f"{base}/photo", files={"file": ("not-a-photo.pdf", PDF)})
    ).status_code == 415
    made = await hr.post(f"{base}/photo", files={"file": ("photo.png", png(), "image/png")})
    assert made.status_code == 204, made.text
    assert (await hr.get(base)).json()["has_photo"] is True
    photo = await hr.get(f"{base}/photo")
    assert photo.status_code == 200
    assert photo.content == png()
    assert photo.headers["content-type"] == "image/png"
    assert photo.headers["cache-control"] == "private, no-store"
    assert (await hr.get(f"{API}/employees/{other}/photo")).status_code == 404
    assert (
        await hr.post(f"{API}/employees/{other}/photo", files={"file": ("photo.png", png())})
    ).status_code == 404
    me = await rig["person"]("employee", rig["a"])
    assert (await me.get(f"{base}/photo")).status_code == 404
    assert (await me.post(f"{base}/photo", files={"file": ("photo.png", png())})).status_code == 403
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update memberships set employee_id=:e where company_id=:c and role='employee'"),
            {"e": emp, "c": rig["a"]},
        )
    assert (await me.get(f"{base}/photo")).status_code == 200
    async with rig["owner"].connect() as c:
        actions = set(
            (
                await c.execute(
                    text("select action from audit_events where entity_id=:e"), {"e": emp}
                )
            ).scalars()
        )
    assert "employee.photo_changed" in actions
