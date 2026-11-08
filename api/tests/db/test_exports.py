"""T16.4: a company's data export, built by the real worker. Only the company's own rows, no secret
columns, step-up before asking, one at a time, a 7-day link that needs the requester's session."""

from __future__ import annotations

import io
import uuid
import zipfile
from typing import Any

from arq.worker import Worker
from sqlalchemy import text

from app.jobs.audit import JobAudit
from app.jobs.queue import open_queue
from app.jobs.scheduled import functions
from tests.db.test_employee_documents import _keys as _keys
from tests.db.test_employee_documents import rig as rig

API = "/api/v1"


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
        assert f"{loose_id},loose-a.txt" in archive.read("documents.csv").decode()

        # Secret, network and storage columns never leave the system.
        def header(path: str) -> set[str]:
            return set(archive.read(path).decode().splitlines()[0].split(","))

        assert "storage_key" not in header("tables/files.csv")
        assert "token_hash" not in header("tables/invitations.csv")
        assert not {"ip", "user_agent"} & header("tables/audit_events.csv")
        assert not any(name.startswith("tables/sessions") for name in names)
        assert "account_number" not in header("tables/employee_bank_details.csv")

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
