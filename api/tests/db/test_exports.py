"""T16.4: a company's data export, built by the real worker. Only the company's own rows, no secret
columns, step-up before asking, one at a time, a 7-day link that needs the requester's session."""

from __future__ import annotations

import csv
import io
import uuid
import zipfile
from typing import Any

import pytest
from arq.worker import Worker
from sqlalchemy import text

from app.jobs.audit import JobAudit
from app.jobs.queue import open_queue
from app.jobs.scheduled import functions
from app.modules.exports.archive import csv_text
from tests.db.test_employee_documents import _keys as _keys
from tests.db.test_employee_documents import rig as rig

API = "/api/v1"


def test_archive_csv_writes_formula_like_user_text_as_text() -> None:
    values = ["=1+1", " +1", "\uff1d1+1", "\nline", 'ordinary,"value"']
    csv_body = csv_text(["name"], [[value] for value in values]).decode()
    assert list(csv.reader(io.StringIO(csv_body))) == [
        ["name"],
        *[["'" + value] for value in values[:-1]],
        [values[-1]],
    ]


async def run(rig: dict[str, Any]) -> None:
    queue = await open_queue(rig["app"].state.settings)
    ctx = {
        "settings": rig["app"].state.settings,
        "engine": rig["app"].state.engine,
        "storage": rig["app"].state.files.storage,
        "owner_engine": rig["owner"],
        "audit": JobAudit(rig["owner"]),
        "redis": queue._pool,
    }
    try:
        worker = Worker(
            functions=functions(),
            redis_pool=queue._pool,
            burst=True,
            handle_signals=False,
            ctx=ctx,
            poll_delay=0.05,
        )
        await worker.async_run()
        assert worker.jobs_failed == 0
    finally:
        await queue.close()


async def step_up(rig: dict[str, Any], client: Any) -> None:
    """Confirms the person just now, as the step-up screen does, without a password."""
    token = client.cookies.get("brand_session")
    data = await rig["sessions"].get(token)
    assert data is not None
    await rig["sessions"].mark_step_up(token, data)


async def _document(
    rig: dict[str, Any], company: uuid.UUID, name: str, owner: str | None = "company_document"
) -> tuple[uuid.UUID, bytes]:
    body = f"the text of {name}".encode()
    key = f"company/{company}/{uuid.uuid4().hex}"
    await rig["app"].state.files.storage.put(
        key, io.BytesIO(body), content_type="text/plain", size=len(body)
    )
    async with rig["owner"].begin() as c:
        file_id = (
            await c.execute(
                text(
                    "insert into files (company_id, storage_key, original_name, mime, size, sha256, "
                    "scan_status, scanned_at, owner_type, category) values (:c, :k, :n, 'text/plain', "
                    ":s, 'a' || repeat('0', 63), 'clean', now(), :o, 'other') "
                    "returning id"
                ),
                {"c": company, "k": key, "n": name, "s": len(body), "o": owner},
            )
        ).scalar_one()
    return file_id, body


async def _seed(rig: dict[str, Any]) -> dict[str, tuple[uuid.UUID, bytes]]:
    async with rig["owner"].begin() as c:
        for company, name in ((rig["a"], "Dept A"), (rig["b"], "Dept B")):
            await c.execute(
                text("insert into departments (company_id, name) values (:c, :n)"),
                {"c": company, "n": name},
            )
    return {
        "a": await _document(rig, rig["a"], "contract-a.txt"),
        "b": await _document(rig, rig["b"], "contract-b.txt"),
        # A document with no owner is still the company's, so it is exported too.
        "loose": await _document(rig, rig["a"], "loose-a.txt", owner=None),
    }


async def _scalar(rig: dict[str, Any], sql: str, **params: Any) -> Any:
    async with rig["owner"].connect() as c:
        return (await c.execute(text(sql), params)).scalar_one()


async def test_export_holds_only_the_requesters_company_and_no_secrets(
    rig: dict[str, Any],
) -> None:
    documents = await _seed(rig)
    admin = await rig["person"]("company_admin", rig["a"])
    other = await rig["person"]("company_admin", rig["b"])
    await step_up(rig, admin)

    requested = await admin.post(f"{API}/companies/me/export")
    assert requested.status_code == 202, requested.text
    export = requested.json()
    assert export["status"] == "queued"
    await run(rig)

    ready = (await admin.get(f"{API}/companies/me/exports/{export['id']}")).json()
    assert ready["status"] == "ready"
    assert ready["expires_at"] is not None

    storage = rig["app"].state.files.storage
    key = await _scalar(
        rig,
        "select f.storage_key from files f join data_exports e on e.file_id = f.id where e.id = :e",
        e=uuid.UUID(export["id"]),
    )
    with zipfile.ZipFile(io.BytesIO(await storage.read(key))) as archive:
        names = set(archive.namelist())
        assert {
            "README.txt",
            "documents.csv",
            "tables/companies.csv",
            "tables/departments.csv",
            "tables/memberships.csv",
        } <= names
        everything = b"".join(archive.read(name) for name in names)
        departments = archive.read("tables/departments.csv").decode()
        assert "Dept A" in departments
        assert "Dept B" not in departments
        assert str(rig["b"]).encode() not in everything  # nothing of company b
        assert b"Dept B" not in everything
        assert b"contract-b.txt" not in everything
        # Company a's document is in the zip, byte for byte.
        file_id, body = documents["a"]
        assert archive.read(f"documents/{file_id}/contract-a.txt") == body
        loose_id, loose_body = documents["loose"]
        assert archive.read(f"documents/{loose_id}/loose-a.txt") == loose_body
        index = csv.DictReader(io.StringIO(archive.read("documents.csv").decode()))
        assert any(
            entry["id"] == str(loose_id) and entry["original_name"] == "loose-a.txt"
            for entry in index
        )

        # Secret, network and storage columns never leave the system.
        def header(path: str) -> set[str]:
            return set(next(csv.reader(io.StringIO(archive.read(path).decode()))))

        assert "storage_key" not in header("tables/files.csv")
        assert "token_hash" not in header("tables/invitations.csv")
        assert not {"ip", "user_agent"} & header("tables/audit_events.csv")
        assert not any(name.startswith("tables/sessions") for name in names)
        assert "account_number" not in header("tables/employee_bank_details.csv")
        # No table in the export carries a deletion code's hash (C3.1.16).
        for name in names:
            if name.startswith("tables/"):
                assert "code_hash" not in header(name), name

    # The link is the API's, and it sends the requester to a 60-second link to the zip.
    redirect = await admin.get(
        f"{API}/companies/me/exports/{export['id']}/download", follow_redirects=False
    )
    assert redirect.status_code == 302
    assert "X-Amz-Expires=60" in redirect.headers["location"]
    assert redirect.headers["cache-control"] == "no-store"

    # Another company's admin cannot see or download it.
    assert (await other.get(f"{API}/companies/me/exports/{export['id']}")).status_code == 404
    assert (
        await other.get(
            f"{API}/companies/me/exports/{export['id']}/download", follow_redirects=False
        )
    ).status_code == 404

    # The requester is e-mailed the link; the actions are audited.
    async with rig["owner"].connect() as c:
        mail = (
            (
                await c.execute(
                    text(
                        "select to_address from email_outbox where template = 'data_export_ready' "
                        "and to_address like 'company_admin-%'"  # not the e-mail samples' address
                    )
                )
            )
            .scalars()
            .all()
        )
        actions = set(
            (
                await c.execute(
                    text("select action from audit_events where company_id = :c"), {"c": rig["a"]}
                )
            ).scalars()
        )
    assert len(mail) == 1
    assert mail[0].startswith("company_admin-")
    assert {"export.requested", "export.generated", "export.downloaded"} <= actions


async def test_asking_needs_step_up_and_the_company_export_permission(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    hr = await rig["person"]("hr_admin", rig["a"])
    refused = await admin.post(f"{API}/companies/me/export")
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "STEP_UP_REQUIRED"
    assert (await hr.post(f"{API}/companies/me/export")).status_code == 403

    await step_up(rig, admin)
    accepted = await admin.post(f"{API}/companies/me/export")
    assert accepted.status_code == 202, accepted.text
    again = await admin.post(f"{API}/companies/me/export")
    assert (again.status_code, again.json()["error"]["code"]) == (409, "EXPORT_IN_PROGRESS")


async def test_an_expired_export_is_marked_and_cannot_be_downloaded(rig: dict[str, Any]) -> None:
    await _seed(rig)
    admin = await rig["person"]("company_admin", rig["a"])
    await step_up(rig, admin)
    export_id = (await admin.post(f"{API}/companies/me/export")).json()["id"]
    await run(rig)
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update data_exports set expires_at = now() - interval '1 minute' where id = :e"),
            {"e": uuid.UUID(export_id)},
        )
    expired = (await admin.get(f"{API}/companies/me/exports/{export_id}")).json()
    assert expired["status"] == "expired"
    gone = await admin.get(
        f"{API}/companies/me/exports/{export_id}/download", follow_redirects=False
    )
    assert (gone.status_code, gone.json()["error"]["code"]) == (410, "EXPORT_EXPIRED")


@pytest.mark.parametrize("role", ["company_admin", "hr_admin"])
@pytest.mark.parametrize("expired", [False, True])
async def test_generic_file_routes_never_expose_company_export_artifacts(
    rig: dict[str, Any], role: str, expired: bool
) -> None:
    """Export permission, requester binding and expiry must not be bypassed via /files."""
    requester = await rig["person"]("company_admin", rig["a"])
    await step_up(rig, requester)
    requested = await requester.post(f"{API}/companies/me/export")
    assert requested.status_code == 202, requested.text
    export_id = uuid.UUID(requested.json()["id"])
    await run(rig)
    file_id = await _scalar(rig, "select file_id from data_exports where id = :e", e=export_id)
    assert file_id is not None
    if expired:
        async with rig["owner"].begin() as connection:
            await connection.execute(
                text(
                    "update data_exports set expires_at = now() - interval '1 minute' where id = :e"
                ),
                {"e": export_id},
            )
    other = await rig["person"](role, rig["a"])
    for browser in (requester, other):
        for suffix in ("", "/download"):
            response = await browser.get(f"{API}/files/{file_id}{suffix}")
            assert response.status_code == 404, response.text
            assert "url" not in response.json()
    assert (
        await _scalar(
            rig,
            "select count(*) from audit_events where entity_id = :f and action = 'file.downloaded'",
            f=file_id,
        )
        == 0
    )


async def test_a_large_document_is_copied_into_the_archive_in_pieces() -> None:
    """ISS-33: peak memory follows the piece size, not the file size, and the bytes match."""
    import hashlib
    import tempfile
    import tracemalloc
    from types import SimpleNamespace
    from typing import cast

    from app.integrations.storage import Storage
    from app.modules.exports.archive import _write_document
    from app.modules.files.models import File

    piece, pieces = b"x" * (1 << 16), 512  # 32 MiB in 64 KiB pieces
    expected = hashlib.sha256(piece * pieces).hexdigest()

    class Pieces:
        async def open(self, key: str) -> Any:
            async def body() -> Any:
                for _ in range(pieces):
                    yield piece

            return body()

    record = cast("File", SimpleNamespace(storage_key="k"))
    with tempfile.TemporaryFile() as target:
        tracemalloc.start()
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            assert await _write_document(
                archive, cast("Storage", Pieces()), record, "documents/big"
            )
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        target.seek(0)
        with zipfile.ZipFile(target) as archive, archive.open("documents/big") as entry:
            digest = hashlib.sha256()
            for chunk in iter(lambda: entry.read(1 << 20), b""):
                digest.update(chunk)
    assert digest.hexdigest() == expected
    assert peak < 4 * (1 << 20)  # well under the 32 MiB file
