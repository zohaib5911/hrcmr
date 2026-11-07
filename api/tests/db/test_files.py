"""T2.7: the upload pipeline against a real object store (RustFS) and a real ClamAV.

A clean PDF is accepted; the EICAR test file and a file whose first bytes do not match its name are
refused; a scanner that cannot be reached refuses everything; links last 60 seconds; the clean-up
job removes only what no row points to.
"""

from __future__ import annotations

import io
import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.core.crypto import KeyRing, set_keyring
from app.db.ids import uuid7
from app.db.session import GlobalSession
from app.integrations.storage import PRESIGN_SECONDS, Storage
from app.main import create_app
from app.modules.auth.sessions import SessionStore
from app.modules.files.service import KEY_PREFIX, remove_orphans
from app.modules.files.validation import MAX_BYTES
from tests.db.support import DatabaseUnderTest, engine_for
from tests.support import TEST_REDIS_URL, build_settings

S3_ENDPOINT = os.environ.get("TEST_S3_ENDPOINT", "http://localhost:9000")
S3_BUCKET = os.environ.get("TEST_S3_BUCKET", "files-dev")
# The throwaway credentials of the local object store (docker-compose.yml); CI starts the same one.
S3_ACCESS = os.environ.get("RUSTFS_ACCESS_KEY", "rustfsadmin")
S3_SECRET = os.environ.get("RUSTFS_SECRET_KEY", "rustfsadmin")
CLAMAV_PORT = int(os.environ.get("TEST_CLAMAV_PORT", "3310"))

PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
# The industry's harmless antivirus test string, assembled here so no scanner flags this source file.
EICAR = ("X5O!P%@AP[4\\PZX54(P^)7CC)7}$" + "EICAR-STANDARD-ANTIVIRUS-TEST-FILE" + "!$H+H*").encode()


@pytest.fixture(autouse=True)
def _keys() -> Any:
    set_keyring(KeyRing(keys={"k1": os.urandom(32)}, active_kid="k1", blind_key=os.urandom(32)))
    yield
    set_keyring(None)


def _settings(clamav_port: int = CLAMAV_PORT, **overrides: Any) -> Settings:
    return build_settings(
        redis_url=TEST_REDIS_URL,
        r2_endpoint=S3_ENDPOINT,
        r2_access_key_id=S3_ACCESS,
        r2_secret_access_key=S3_SECRET,
        r2_bucket_files=S3_BUCKET,
        clamav_host="localhost",
        clamav_port=clamav_port,
        **overrides,
    )


def _storage() -> Storage:
    storage = Storage.from_settings(_settings())
    assert storage is not None
    return storage


@pytest.fixture
async def api(database: DatabaseUnderTest) -> AsyncIterator[dict[str, Any]]:
    redis = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    await redis.flushdb()
    a, b = uuid7(), uuid7()
    owner = engine_for(database.owner_url, poolclass=NullPool)
    async with owner.begin() as c:
        await c.execute(text("truncate users, companies cascade"))
        for ident, slug in ((a, "a"), (b, "b")):
            await c.execute(
                text("insert into companies (id, name, slug) values (:i, :n, :s)"),
                {"i": ident, "n": f"Company {slug}", "s": slug},
            )
    await owner.dispose()
    sessions = SessionStore(redis)
    clients: list[httpx.AsyncClient] = []

    def start(clamav_port: int) -> Any:
        return create_app(_settings(clamav_port, database_url=database.app_url))

    async def person(app: Any, role: str, company: uuid.UUID) -> httpx.AsyncClient:
        user = uuid7()
        owner = engine_for(database.owner_url, poolclass=NullPool)
        async with owner.begin() as c:
            await c.execute(
                text(
                    "insert into users (id, email, first_name, last_name, password_hash, "
                    "email_verified_at) values (:u, :e, 'Ann', :r, 'x', now())"
                ),
                {"u": user, "e": f"{role}-{user}@example.com", "r": role},
            )
            await c.execute(
                text("insert into memberships (user_id, company_id, role) values (:u, :c, :r)"),
                {"u": user, "c": company, "r": role},
            )
            await c.execute(
                text(
                    "insert into terms_acceptances (user_id, version) "
                    "select :u, version from terms_versions"
                ),
                {"u": user},
            )
        await owner.dispose()
        engine = engine_for(database.app_url, poolclass=NullPool)
        async with GlobalSession(engine) as db:
            token, _ = await sessions.create(
                db, user_id=user, company_id=company, ip=None, user_agent=None, mfa_passed=True
            )
            await db.commit()
        await engine.dispose()
        browser = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        )
        browser.cookies.set("brand_session", token)
        browser.cookies.set("csrf", "t")
        browser.headers["X-CSRF-Token"] = "t"
        clients.append(browser)
        return browser

    yield {"start": start, "person": person, "a": a, "b": b, "db": database}
    for client in clients:
        await client.aclose()
    await redis.flushdb()
    await redis.aclose()


async def _upload(
    client: httpx.AsyncClient, name: str, body: bytes, **fields: str
) -> httpx.Response:
    return await client.post(
        "/api/v1/files", files={"file": (name, body, "application/octet-stream")}, data=fields
    )


async def _rows(database: DatabaseUnderTest, company: uuid.UUID) -> list[Any]:
    owner = engine_for(database.owner_url, poolclass=NullPool)
    try:
        async with owner.connect() as c:
            result = await c.execute(
                text("select * from files where company_id = :c"), {"c": company}
            )
            return list(result.mappings())
    finally:
        await owner.dispose()


async def _actions(database: DatabaseUnderTest, company: uuid.UUID) -> list[str]:
    owner = engine_for(database.owner_url, poolclass=NullPool)
    try:
        async with owner.connect() as c:
            result = await c.execute(
                text("select action from audit_events where company_id = :c order by created_at"),
                {"c": company},
            )
            return [row[0] for row in result]
    finally:
        await owner.dispose()


async def test_a_clean_pdf_is_accepted_stored_and_served_for_sixty_seconds(
    api: dict[str, Any],
) -> None:
    app = api["start"](CLAMAV_PORT)
    async with LifespanManager(app):
        admin = await api["person"](app, "hr_admin", api["a"])
        sent = await _upload(admin, "contract.pdf", PDF, category="contract")
        assert sent.status_code == 201, sent.text
        body = sent.json()
        assert body["scan_status"] == "clean"
        assert body["mime"] == "application/pdf"
        assert body["size"] == len(PDF)

        (row,) = await _rows(api["db"], api["a"])
        assert row["storage_key"].startswith(f"{KEY_PREFIX}{api['a']}/")
        assert "contract" not in row["storage_key"]  # random, never the file's name
        assert await _storage().exists(row["storage_key"])

        link = await admin.get(f"/api/v1/files/{body['id']}/download")
        assert link.status_code == 200
        assert link.json()["expires_in"] == PRESIGN_SECONDS == 60
        assert "X-Amz-Expires=60" in link.json()["url"]
        async with httpx.AsyncClient() as plain:
            served = await plain.get(link.json()["url"])
        assert served.status_code == 200
        assert served.content == PDF
        assert served.headers["content-disposition"].startswith("attachment")

        assert await _actions(api["db"], api["a"]) == ["file.uploaded", "file.downloaded"]
        await _storage().delete(row["storage_key"])


async def test_the_eicar_test_file_is_rejected_and_nothing_is_kept(api: dict[str, Any]) -> None:
    app = api["start"](CLAMAV_PORT)
    async with LifespanManager(app):
        admin = await api["person"](app, "hr_admin", api["a"])
        refused = await _upload(admin, "notes.csv", EICAR)
        assert refused.status_code == 422
        assert refused.json()["error"]["code"] == "FILE_INFECTED"
        assert await _rows(api["db"], api["a"]) == []
        assert await _storage().list_objects(f"{KEY_PREFIX}{api['a']}/") == []
        assert await _actions(api["db"], api["a"]) == ["file.upload.rejected"]


async def test_a_wrong_magic_byte_is_rejected(api: dict[str, Any]) -> None:
    app = api["start"](CLAMAV_PORT)
    async with LifespanManager(app):
        admin = await api["person"](app, "hr_admin", api["a"])
        program = b"MZ\x90\x00\x03\x00\x00\x00" + os.urandom(64)  # a Windows program named .pdf
        refused = await _upload(admin, "invoice.pdf", program)
        assert refused.status_code == 415
        assert refused.json()["error"]["code"] == "FILE_TYPE_MISMATCH"
        not_listed = await _upload(admin, "setup.exe", program)
        assert not_listed.json()["error"]["code"] == "FILE_TYPE_NOT_ALLOWED"
        assert await _rows(api["db"], api["a"]) == []


async def test_too_big_or_empty_files_are_refused(api: dict[str, Any]) -> None:
    app = api["start"](CLAMAV_PORT)
    async with LifespanManager(app):
        admin = await api["person"](app, "hr_admin", api["a"])
        empty = await _upload(admin, "a.pdf", b"")
        assert empty.json()["error"]["code"] == "FILE_EMPTY"
        big = await _upload(admin, "a.pdf", PDF + b"\0" * (MAX_BYTES - len(PDF) + 1))
        assert big.status_code == 413
        assert big.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
        huge = await _upload(admin, "a.pdf", PDF + b"\0" * (27 * 1024 * 1024))
        assert huge.status_code == 413  # cut off by the body limit before it is even read
        assert huge.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
        assert await _rows(api["db"], api["a"]) == []


async def test_when_the_scanner_cannot_be_reached_nothing_is_accepted(api: dict[str, Any]) -> None:
    app = api["start"](1)  # nothing listens here
    async with LifespanManager(app):
        admin = await api["person"](app, "hr_admin", api["a"])
        refused = await _upload(admin, "contract.pdf", PDF)
        assert refused.status_code == 503
        assert refused.json()["error"]["code"] == "SCAN_UNAVAILABLE"
        assert await _rows(api["db"], api["a"]) == []


async def test_another_company_cannot_see_the_file_and_an_employee_only_their_own(
    api: dict[str, Any],
) -> None:
    app = api["start"](CLAMAV_PORT)
    async with LifespanManager(app):
        admin = await api["person"](app, "hr_admin", api["a"])
        other = await api["person"](app, "hr_admin", api["b"])
        staff = await api["person"](app, "employee", api["a"])
        made = await _upload(admin, "contract.pdf", PDF)
        file_id = made.json()["id"]
        assert (await other.get(f"/api/v1/files/{file_id}")).status_code == 404
        assert (await other.get(f"/api/v1/files/{file_id}/download")).status_code == 404
        # An employee reaches neither someone else's file, nor may attach a file to no one.
        assert (await staff.get(f"/api/v1/files/{file_id}")).status_code == 404
        assert (await _upload(staff, "mine.pdf", PDF)).status_code == 403
        (row,) = await _rows(api["db"], api["a"])
        await _storage().delete(row["storage_key"])


async def test_the_cleanup_removes_only_objects_no_row_points_to(
    api: dict[str, Any],
) -> None:
    app = api["start"](CLAMAV_PORT)
    storage = _storage()
    async with LifespanManager(app):
        admin = await api["person"](app, "hr_admin", api["a"])
        made = await _upload(admin, "contract.pdf", PDF)
        assert made.status_code == 201
        (row,) = await _rows(api["db"], api["a"])
        stray = f"{KEY_PREFIX}{api['a']}/{uuid.uuid4().hex}"
        owner = engine_for(api["db"].owner_url, poolclass=NullPool)
        try:
            # The bucket is shared across runs, so sweep leftovers from earlier runs first; the checks
            # below then see only this test's objects.
            await remove_orphans(storage, owner, now=datetime.now(UTC) + timedelta(days=2))
            await storage.put(stray, io.BytesIO(b"left behind"), content_type="text/csv", size=11)
            # Recent objects are left alone, in case an upload is still in progress.
            assert await remove_orphans(storage, owner) == 0
            assert await storage.exists(stray)
            later = datetime.now(UTC) + timedelta(days=2)
            assert await remove_orphans(storage, owner, now=later) >= 1
        finally:
            await owner.dispose()
        assert not await storage.exists(stray)
        assert await storage.exists(row["storage_key"])  # it has a row, so it stays
        await storage.delete(row["storage_key"])


async def test_attendance_import_file_is_not_kept_by_a_demoted_uploader(
    api: dict[str, Any],
) -> None:
    app = api["start"](CLAMAV_PORT)
    async with LifespanManager(app):
        admin = await api["person"](app, "hr_admin", api["a"])
        sent = await _upload(
            admin,
            "attendance.csv",
            b"employee_number,date,status,clock_in,clock_out,note\nE1,2026-11-03,sick,,,\n",
            owner_type="attendance_import",
            owner_id=str(uuid.uuid4()),
            category="attendance_import",
        )
        assert sent.status_code == 201, sent.text
        ident = sent.json()["id"]
        assert (await admin.get(f"/api/v1/files/{ident}")).status_code == 200
        user = (await admin.get("/api/v1/auth/me")).json()["user"]["id"]
        owner = engine_for(api["db"].owner_url, poolclass=NullPool)
        try:
            async with owner.begin() as c:
                await c.execute(
                    text(
                        "update memberships set role='employee' where user_id=:u and company_id=:c"
                    ),
                    {"u": uuid.UUID(user), "c": api["a"]},
                )
        finally:
            await owner.dispose()
        assert (await admin.get(f"/api/v1/files/{ident}")).status_code == 404
        assert (await admin.get(f"/api/v1/files/{ident}/download")).status_code == 404
