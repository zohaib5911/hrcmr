"""T10.2: real ARQ report jobs, durable recovery, private artifacts and authorization changes."""

from __future__ import annotations

import io
import json
import uuid
from typing import Any

import pytest
from arq.worker import Worker
from openpyxl import load_workbook
from sqlalchemy import text

from app.integrations.storage import StorageError
from app.jobs.audit import JobAudit
from app.jobs.queue import open_queue
from app.jobs.reports import generate_report, sweep_report_jobs
from app.jobs.scheduled import functions
from app.modules.reports import router as report_router
from app.modules.reports.reference import REPORT_TYPES
from tests.db.test_employee_documents import _keys as _keys
from tests.db.test_employee_documents import rig as rig

API = "/api/v1/reports"


async def context(rig: dict[str, Any]) -> dict[str, Any]:
    return {
        "engine": rig["app"].state.engine,
        "storage": rig["app"].state.files.storage,
        "owner_engine": rig["owner"],
        "audit": JobAudit(rig["owner"]),
    }


async def run(rig: dict[str, Any], *, sweep: bool = False) -> None:
    queue = await open_queue(rig["app"].state.settings)
    ctx = await context(rig)
    ctx["redis"] = queue._pool
    try:
        if sweep:
            assert await sweep_report_jobs(ctx) >= 1
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


async def test_seven_reports_are_queued_generated_and_downloadable_by_requester(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    for kind in REPORT_TYPES:
        response = await admin.post(API + f"/{kind}")
        assert response.status_code == 202, response.text
        job = response.json()
        assert job["status"] == "queued"
        assert job["url"] is None
        await run(rig)
        ready = await admin.get(API + f"/jobs/{job['id']}")
        assert ready.status_code == 200, ready.text
        assert ready.json()["status"] == "ready"
        assert ready.json()["expires_in"] == 60
        assert "X-Amz-Expires=60" in ready.json()["url"]
        async with rig["owner"].connect() as db:
            artifact = (
                await db.execute(
                    text(
                        "select f.storage_key, f.mime from files f join report_jobs j on j.file_id=f.id where j.id=:j"
                    ),
                    {"j": job["id"]},
                )
            ).one()
        content = await rig["app"].state.files.storage.read(artifact.storage_key)
        book = load_workbook(io.BytesIO(content))
        assert "About this report" in book.sheetnames
        book.close()
        assert await generate_report(await context(rig), str(rig["a"]), job["id"]) == "not_queued"
    assert len((await admin.get(API + "/jobs")).json()) == 7
    async with rig["owner"].connect() as db:
        actions = set(
            (
                await db.execute(
                    text("select action from audit_events where company_id=:c"), {"c": rig["a"]}
                )
            ).scalars()
        )
    assert {"report.requested", "report.generated", "file.downloaded"} <= actions


async def test_job_and_artifact_are_private_and_permissions_rechecked(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    job = (await admin.post(API + "/employee_detail")).json()
    assert await generate_report(await context(rig), str(rig["b"]), job["id"]) == "not_queued"
    await run(rig)
    async with rig["owner"].connect() as db:
        file_id = (
            await db.execute(text("select file_id from report_jobs where id=:j"), {"j": job["id"]})
        ).scalar_one()
    for role, company in [("hr_admin", rig["a"]), ("company_admin", rig["b"])]:
        other = await rig["person"](role, company)
        assert (await other.get(API + f"/jobs/{job['id']}")).status_code == 404
        assert (await other.get(f"/api/v1/files/{file_id}/download")).status_code == 404
    for role in ("employee", "people_manager", "recruiter", "read_only_auditor"):
        other = await rig["person"](role, rig["a"])
        assert (await other.post(API + "/employee_directory")).status_code == 403
        assert (await other.get(API + "/jobs")).status_code == 403
        assert (await other.get(API + f"/jobs/{job['id']}")).status_code == 403
    async with rig["owner"].begin() as db:
        await db.execute(
            text(
                "update memberships set role='employee' where company_id=:c and user_id=(select requested_by from report_jobs where id=:j)"
            ),
            {"c": rig["a"], "j": job["id"]},
        )
    assert (await admin.get(API + f"/jobs/{job['id']}")).status_code == 403
    assert (await admin.get(f"/api/v1/files/{file_id}/download")).status_code == 404


async def test_revoked_request_is_failed_before_generation(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("hr_admin", rig["a"])
    job = (await admin.post(API + "/employee_directory")).json()
    async with rig["owner"].begin() as db:
        await db.execute(
            text(
                "update memberships set status='suspended' where company_id=:c and role='hr_admin'"
            ),
            {"c": rig["a"]},
        )
    await run(rig)
    async with rig["owner"].connect() as db:
        result = (
            await db.execute(
                text("select status, error_code, file_id from report_jobs where id=:j"),
                {"j": job["id"]},
            )
        ).one()
    assert result.status == "failed"
    assert result.error_code == "ACCESS_REVOKED"
    assert result.file_id is None


async def test_durable_sweep_recovers_missed_enqueue_and_limit_is_bounded(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])

    async def unavailable(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("queue unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(report_router, "open_queue", unavailable)
        first = await admin.post(API + "/company")
        assert first.status_code == 202, first.text
        assert (await admin.post(API + "/leave_taken")).status_code == 202
        assert (await admin.post(API + "/training_completion")).status_code == 202
        full = await admin.post(API + "/employee_directory")
        assert full.status_code == 429
        assert full.json()["error"]["code"] == "REPORT_QUEUE_FULL"
    await run(rig, sweep=True)
    assert (await admin.get(API + f"/jobs/{first.json()['id']}")).json()["status"] == "ready"
    assert (await admin.post(API + "/not-a-report")).status_code == 422
    assert (await admin.get(API + f"/jobs/{uuid.uuid4()}")).status_code == 404


async def test_storage_failure_rolls_back_artifact_and_does_not_leak_details(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    job = (await admin.post(API + "/employee_directory")).json()

    async def fail(*args: Any, **kwargs: Any) -> None:
        raise StorageError("private test storage detail")

    monkeypatch.setattr(rig["app"].state.files.storage, "put", fail)
    await run(rig)
    state = (await admin.get(API + f"/jobs/{job['id']}")).json()
    assert state["status"] == "failed"
    assert state["error_code"] == "REPORT_FAILED"
    assert state["url"] is None
    async with rig["owner"].connect() as db:
        assert (
            await db.execute(
                text("select count(*) from files where company_id=:c"), {"c": rig["a"]}
            )
        ).scalar_one() == 0
        events = (
            (
                await db.execute(
                    text("select after from audit_events where company_id=:c"), {"c": rig["a"]}
                )
            )
            .scalars()
            .all()
        )
    assert "private test storage detail" not in json.dumps(events, default=str)


async def test_worker_audit_failure_rolls_back_artifact(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.jobs import reports as report_jobs

    admin = await rig["person"]("company_admin", rig["a"])
    job = (await admin.post(API + "/company")).json()
    original = report_jobs.record

    async def fail(*args: Any, **kwargs: Any) -> None:
        if args[2] == "report.generated":
            raise RuntimeError("audit unavailable")
        await original(*args, **kwargs)

    monkeypatch.setattr(report_jobs, "record", fail)
    await run(rig)
    assert (await admin.get(API + f"/jobs/{job['id']}")).json()["status"] == "failed"
    async with rig["owner"].connect() as db:
        assert (
            await db.execute(
                text("select count(*) from files where company_id=:c"), {"c": rig["a"]}
            )
        ).scalar_one() == 0
        actions = set(
            (
                await db.execute(
                    text("select action from audit_events where company_id=:c"), {"c": rig["a"]}
                )
            ).scalars()
        )
    assert "report.generated" not in actions
    assert "report.failed" in actions
