"""T9.2 real scanned upload, reviewed import and atomic/stale/tenant safeguards."""

from __future__ import annotations

import asyncio
import io
import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from asgi_lifespan import LifespanManager
from openpyxl import Workbook
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from tests.db.support import engine_for
from tests.db.test_files import CLAMAV_PORT, EICAR
from tests.db.test_files import _keys as _keys
from tests.db.test_files import api as api

BASE = "/api/v1/attendance/import"
CSV = b"employee_number,date,status,clock_in,clock_out,note\nA001,2026-11-03,Present,09:00,17:00,Private note\n"


@pytest.fixture
async def imports(api: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
    app = api["start"](CLAMAV_PORT)
    async with LifespanManager(app):
        admin = await api["person"](app, "hr_admin", api["a"])
        foreign = await api["person"](app, "company_admin", api["b"])
        person = await admin.post(
            "/api/v1/employees",
            json={
                "first_name": "Amira",
                "last_name": "Import",
                "employee_number": "A001",
                "email": "a@example.com",
                "hire_date": "2025-01-01",
            },
        )
        assert person.status_code == 201, person.text
        owner = engine_for(api["db"].owner_url, poolclass=NullPool)
        try:
            yield {
                **api,
                "app": app,
                "admin": admin,
                "foreign": foreign,
                "employee": person.json()["id"],
                "owner": owner,
            }
        finally:
            await owner.dispose()


async def preview(
    imports: dict[str, Any], content: bytes = CSV, name: str = "attendance.csv"
) -> Any:
    return await imports["admin"].post(
        BASE + "/preview", files={"file": (name, content, "application/octet-stream")}
    )


async def test_preview_no_attendance_writes_commit_and_concurrent_retry(
    imports: dict[str, Any],
) -> None:
    response = await preview(imports)
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["rows_valid"] == row["rows_total"] == 1
    assert row["rows"][0]["employee_name"] == "Amira Import"
    assert row["rows"][0]["action"] == "create"
    async with imports["owner"].connect() as c:
        assert (await c.execute(text("select count(*) from attendance_records"))).scalar_one() == 0
        assert (await c.execute(text("select scan_status from files"))).scalar_one() == "clean"
    replies = await asyncio.gather(
        *(imports["admin"].post(BASE + f"/{row['id']}/commit") for _ in range(2))
    )
    assert [r.status_code for r in replies] == [200, 200]
    assert replies[0].json()["committed_at"] == replies[1].json()["committed_at"]
    listed = await imports["admin"].get(
        "/api/v1/attendance-records?start=2026-11-03&end=2026-11-03"
    )
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["source"] == "import"
    assert listed.json()["items"][0]["hours"] == "8.00"
    async with imports["owner"].connect() as c:
        audits = (
            (
                await c.execute(
                    text("select after from audit_events where company_id=:c"), {"c": imports["a"]}
                )
            )
            .scalars()
            .all()
        )
        assert "Private note" not in json.dumps(audits)
        assert (
            await c.execute(
                text("select count(*) from audit_events where action='attendance.import_committed'")
            )
        ).scalar_one() == 1


async def test_preview_errors_duplicates_and_foreign_import_ids(imports: dict[str, Any]) -> None:
    content = (
        CSV
        + b"A001,2026-11-03,Present,09:00,17:00,Duplicate\nNOPE,2026-11-03,Sick,,,\nA001,not-a-date,Sick,,,\n"
    )
    response = await preview(imports, content)
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["rows_valid"] == 0
    assert all(r["errors"] for r in row["rows"])
    assert (await imports["admin"].post(BASE + f"/{row['id']}/commit")).status_code == 409
    for suffix in ("", "/commit"):
        url = BASE + f"/{row['id']}" + suffix
        response = await (imports["foreign"].post(url) if suffix else imports["foreign"].get(url))
        assert response.status_code == 404, response.text
    employee = await imports["person"](imports["app"], "employee", imports["a"])
    assert (await employee.get(BASE + "/template.csv")).status_code == 403
    assert (await employee.get(BASE + f"/{row['id']}")).status_code == 403
    async with imports["owner"].connect() as c:
        assert (await c.execute(text("select count(*) from attendance_records"))).scalar_one() == 0


async def test_stale_rows_company_zone_and_leave_sync_are_rechecked(
    imports: dict[str, Any],
) -> None:
    row = (await preview(imports)).json()
    changed = await imports["admin"].put(
        "/api/v1/attendance-records",
        json={
            "employee_id": imports["employee"],
            "date": "2026-11-03",
            "status": "present",
            "clock_in": "09:00",
            "clock_out": "18:00",
        },
    )
    assert changed.status_code == 200, changed.text
    assert (await imports["admin"].post(BASE + f"/{row['id']}/commit")).status_code == 409
    fresh = (await preview(imports)).json()
    assert fresh["rows"][0]["action"] == "update"
    async with imports["owner"].begin() as c:
        await c.execute(
            text("update companies set timezone='Asia/Karachi' where id=:c"), {"c": imports["a"]}
        )
    assert (await imports["admin"].post(BASE + f"/{fresh['id']}/commit")).status_code == 409
    async with imports["owner"].begin() as c:
        await c.execute(text("update attendance_records set source='leave_sync'"))
    protected = await preview(imports)
    assert protected.status_code == 201, protected.text
    assert protected.json()["rows_valid"] == 0
    assert "Approved leave" in protected.json()["rows"][0]["errors"][0]


async def test_commit_audit_failure_rolls_back_every_row(
    imports: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    row = (await preview(imports)).json()

    async def broken(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr("app.modules.rbac.deps.record_audit", broken)
    assert (await imports["admin"].post(BASE + f"/{row['id']}/commit")).status_code == 500
    async with imports["owner"].connect() as c:
        assert (await c.execute(text("select count(*) from attendance_records"))).scalar_one() == 0
        assert (
            await c.execute(text("select status from attendance_imports"))
        ).scalar_one() == "previewed"


async def test_xlsx_template_formula_errors_and_virus_rejection(imports: dict[str, Any]) -> None:
    template = await imports["admin"].get(BASE + "/template.xlsx")
    assert template.status_code == 200, template.text
    assert template.content.startswith(b"PK")
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(["employee_number", "date", "status", "clock_in", "clock_out", "note"])
    sheet.append(["A001", "2026-11-03", "Present", "09:00", "17:00", "=1+1"])
    buffer = io.BytesIO()
    book.save(buffer)
    book.close()
    response = await preview(imports, buffer.getvalue(), "attendance.xlsx")
    assert response.status_code == 201, response.text
    assert response.json()["rows_valid"] == 0
    assert "formula" in response.json()["rows"][0]["errors"][0]
    infected = await preview(imports, EICAR, "private-sick.csv")
    assert infected.status_code == 422
    assert infected.json()["error"]["code"] == "FILE_INFECTED"
    async with imports["owner"].connect() as c:
        events = (
            await c.execute(
                text("select summary,after from audit_events where action='file.upload.rejected'")
            )
        ).all()
        assert "private-sick" not in str(events)
