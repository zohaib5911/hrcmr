"""T9.2 atomic status grid, permission-scoped reports and recorded absence totals."""

from __future__ import annotations

import io
from typing import Any

import pytest
from openpyxl import load_workbook
from pypdf import PdfReader
from sqlalchemy import text

from tests.db.test_attendance import put
from tests.db.test_compliance_hub import rig as rig
from tests.db.test_leave_requests import BASE, linked, submit
from tests.db.test_leave_requests import ready as ready
from tests.db.test_leave_settings import seeded as seeded
from tests.db.test_reminders import _keys as _keys

API = "/api/v1/attendance"


async def test_grid_reads_are_scoped_and_worked_status_does_not_invent_hours(
    ready: dict[str, Any],
) -> None:
    assert (await put(ready, note="Keep this note")).status_code == 200
    grid = await ready["admin"].get(API + "/grid?start=2026-01-05&limit=1")
    assert grid.status_code == 200, grid.text
    assert grid.json()["next_offset"] == 1
    assert len(grid.json()["people"]) == 1
    response = await ready["admin"].put(
        API + "/grid",
        json={
            "rows": [
                {"employee_id": str(ready["employee"]), "date": "2026-01-06", "status": "present"},
                {"employee_id": str(ready["other"]), "date": "2026-01-06", "status": "absent"},
            ]
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["count"] == 2
    records = await ready["admin"].get("/api/v1/attendance-records?start=2026-01-06&end=2026-01-06")
    assert len(records.json()["items"]) == 2
    assert all(r["source"] == "grid" and r["hours"] is None for r in records.json()["items"])
    preserved = await ready["admin"].put(
        API + "/grid",
        json={
            "rows": [
                {"employee_id": str(ready["employee"]), "date": "2026-01-05", "status": "late"}
            ]
        },
    )
    assert preserved.status_code == 200, preserved.text
    existing = (
        await ready["admin"].get("/api/v1/attendance-records?start=2026-01-05&end=2026-01-05")
    ).json()["items"][0]
    assert existing["status"] == "late"
    assert existing["hours"] == "7.50"
    assert existing["unpaid_break_minutes"] == 30
    assert existing["note"] == "Keep this note"
    me = await linked(ready, "employee", ready["employee"])
    mine = await me.get(API + "/grid?start=2026-01-05")
    assert {p["id"] for p in mine.json()["people"]} == {str(ready["employee"])}
    assert (
        await me.put(
            API + "/grid",
            json={
                "rows": [
                    {"employee_id": str(ready["employee"]), "date": "2026-01-05", "status": "late"}
                ]
            },
        )
    ).status_code == 403
    foreign = await ready["person"]("company_admin", ready["b"])
    assert (await foreign.get(API + "/grid?start=2026-01-05")).json()["records"] == []


async def test_duplicate_foreign_and_leave_rows_reject_entire_grid(ready: dict[str, Any]) -> None:
    row = {"employee_id": str(ready["employee"]), "date": "2026-01-12", "status": "present"}
    assert (await ready["admin"].put(API + "/grid", json={"rows": [row, row]})).status_code == 422
    assert (
        await ready["admin"].put(
            API + "/grid", json={"rows": [row, {**row, "employee_id": str(ready["foreign"])}]}
        )
    ).status_code == 404
    request = await submit(ready)
    assert (
        await ready["admin"].post(BASE + f"/requests/{request['id']}/approve", json={})
    ).status_code == 200
    response = await ready["admin"].put(
        API + "/grid", json={"rows": [row, {**row, "date": "2026-01-05"}]}
    )
    assert response.status_code == 409, response.text
    async with ready["owner"].connect() as c:
        assert (
            await c.execute(text("select count(*) from attendance_records where date='2026-01-12'"))
        ).scalar_one() == 0
        assert (
            await c.execute(
                text("select count(*) from attendance_records where source='leave_sync'")
            )
        ).scalar_one() == 5


async def test_reports_export_safe_spreadsheets_pdf_and_scoped_absence_days(
    ready: dict[str, Any],
) -> None:
    assert (await put(ready, note="=1+1")).status_code == 200
    assert (
        await put(
            ready,
            employee_id=str(ready["other"]),
            status="sick",
            clock_in=None,
            clock_out=None,
            unpaid_break_minutes=0,
        )
    ).status_code == 200
    assert (
        await put(
            ready,
            date="2026-01-06",
            status="half_day",
            clock_in="09:00",
            clock_out="13:00",
            unpaid_break_minutes=0,
        )
    ).status_code == 200
    report = await ready["admin"].get(API + "/export.xlsx?start=2026-01-01&end=2026-01-31")
    assert report.status_code == 200, report.text
    book = load_workbook(io.BytesIO(report.content))
    sheet = book.active
    assert sheet is not None
    assert sheet.max_row == 4
    notes = [row[8] for row in list(sheet.rows)[1:]]
    assert any(cell.value == "=1+1" and cell.data_type == "s" for cell in notes)
    book.close()
    pdf = await ready["admin"].get(API + "/export.pdf?start=2026-01-01&end=2026-01-31")
    assert pdf.status_code == 200, pdf.text
    assert pdf.content.startswith(b"%PDF")
    assert "Attendance report" in " ".join(
        p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages
    )
    absence = await ready["admin"].get(API + "/absences?month=2026-01")
    assert absence.status_code == 200, absence.text
    assert absence.json()["days"] == "1.5"
    assert absence.json()["employees"] == 2
    me = await linked(ready, "employee", ready["employee"])
    own = await me.get(API + "/absences?month=2026-01")
    assert own.json()["days"] == "0.5"
    assert {r["employee_id"] for r in own.json()["records"]} == {str(ready["employee"])}
    assert (await me.get(API + "/export.xlsx?start=2026-01-01&end=2026-01-31")).status_code == 403
    manager = await ready["person"]("people_manager", ready["a"])
    assert (
        await manager.get(API + "/export.pdf?start=2026-01-01&end=2026-01-31")
    ).status_code == 403
    foreign = await ready["person"]("company_admin", ready["b"])
    assert (await foreign.get(API + "/absences?month=2026-01")).json()["records"] == []
    empty = await foreign.get(API + "/export.xlsx?start=2026-01-01&end=2026-01-31")
    empty_book = load_workbook(io.BytesIO(empty.content))
    assert empty_book.active is not None
    assert empty_book.active.max_row == 1
    empty_book.close()
    assert (await ready["admin"].get(API + "/absences?month=0000-01")).status_code == 422


async def test_grid_audit_failure_rolls_back(
    ready: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr("app.modules.rbac.deps.record_audit", broken)
    response = await ready["admin"].put(
        API + "/grid",
        json={
            "rows": [
                {"employee_id": str(ready["employee"]), "date": "2026-01-05", "status": "present"}
            ]
        },
    )
    assert response.status_code == 500
    async with ready["owner"].connect() as c:
        assert (await c.execute(text("select count(*) from attendance_records"))).scalar_one() == 0
