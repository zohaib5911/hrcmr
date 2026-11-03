"""T9.3 own clock boundaries, consent, exact hours and reviewed report approvals."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any

import pytest
from sqlalchemy import text

from app.modules.attendance import clock_router
from app.modules.rbac.deps import Access
from tests.db.test_attendance import put
from tests.db.test_compliance_hub import rig as rig
from tests.db.test_leave_requests import linked
from tests.db.test_leave_requests import ready as ready
from tests.db.test_leave_settings import seeded as seeded
from tests.db.test_reminders import _keys as _keys

API = "/api/v1/attendance"


def at(monkeypatch: pytest.MonkeyPatch, instant: str) -> None:
    monkeypatch.setattr(clock_router, "now", lambda: datetime.fromisoformat(instant))


async def manager_for(ready: dict[str, Any]) -> Any:
    manager = await linked(ready, "people_manager", ready["other"])
    async with ready["owner"].begin() as c:
        await c.execute(
            text(
                "insert into employee_assignments (company_id,employee_id,employment_type,effective_from,reporting_authority_employee_id) values (:c,:e,'full_time','2025-01-01',:m)"
            ),
            {"c": ready["a"], "e": ready["employee"], "m": ready["other"]},
        )
    return manager


async def test_clock_own_server_time_overnight_retries_and_private_audit(
    ready: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    me = await linked(ready, "employee", ready["employee"])
    at(monkeypatch, "2026-03-28T23:00:00+00:00")
    assert (await ready["admin"].post(API + "/clock-in", json={})).status_code == 403
    assert (
        await me.post(API + "/clock-in", json={"employee_id": str(ready["other"])})
    ).status_code == 422
    a, b = await asyncio.gather(
        *[me.post(API + "/clock-in", json={"note": "Private note"}) for _ in range(2)]
    )
    assert a.status_code == b.status_code == 200, (a.text, b.text)
    record = a.json()["active"]
    assert b.json()["active"]["id"] == record["id"]
    assert record["date"] == "2026-03-28"
    assert record["clock_in"] == "2026-03-28T23:00:00Z"
    assert (await me.get(API + "/clock")).json()["active"]["id"] == record["id"]
    blocked = await ready["admin"].put(
        API + "/grid",
        json={
            "rows": [
                {"employee_id": str(ready["employee"]), "date": "2026-03-28", "status": "absent"}
            ]
        },
    )
    assert blocked.status_code == 409
    at(monkeypatch, "2026-03-29T07:00:00+00:00")
    invalid = await me.post(
        API + "/clock-out", json={"record_id": record["id"], "unpaid_break_minutes": 600}
    )
    assert invalid.status_code == 422
    result = await me.post(
        API + "/clock-out",
        json={"record_id": record["id"], "unpaid_break_minutes": 30, "note": "Private out note"},
    )
    assert result.status_code == 200, result.text
    assert result.json()["hours"] == "7.50"
    assert result.json()["clock_out_local"] == "08:00"
    at(monkeypatch, "2026-03-29T08:00:00+00:00")
    retry = await me.post(API + "/clock-out", json={"record_id": record["id"]})
    assert retry.json()["hours"] == "7.50"
    assert (await me.get(API + "/clock")).json()["active"] is None
    foreign = await linked(ready, "employee", ready["other"])
    assert (
        await foreign.post(API + "/clock-out", json={"record_id": record["id"]})
    ).status_code == 404
    async with ready["owner"].connect() as c:
        audits = (
            (
                await c.execute(
                    text(
                        "select after from audit_events where action like 'attendance.clock%' and company_id=:company"
                    ),
                    {"company": ready["a"]},
                )
            )
            .scalars()
            .all()
        )
    assert len(audits) == 2
    assert "Private" not in json.dumps(audits)


async def test_location_needs_company_switch_and_per_action_consent(
    ready: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    at(monkeypatch, "2026-01-05T09:00:00+00:00")
    me = await linked(ready, "employee", ready["employee"])
    geo = {"latitude": 51.5007, "longitude": -0.1246, "accuracy": 25}
    assert (
        await me.post(API + "/clock-in", json={"location": geo, "location_consent": True})
    ).status_code == 403
    assert (
        await ready["admin"].patch("/api/v1/company", json={"clock_geolocation_enabled": True})
    ).status_code == 200
    assert (await me.post(API + "/clock-in", json={"location": geo})).status_code == 403
    assert (
        await me.post(
            API + "/clock-in", json={"location": {**geo, "latitude": 91}, "location_consent": True}
        )
    ).status_code == 422
    response = await me.post(API + "/clock-in", json={"location": geo, "location_consent": True})
    assert response.status_code == 200, response.text
    assert "latitude" not in response.text
    at(monkeypatch, "2026-01-05T17:00:00+00:00")
    assert (
        await me.post(API + "/clock-out", json={"record_id": response.json()["active"]["id"]})
    ).status_code == 200
    async with ready["owner"].connect() as c:
        row = (
            await c.execute(
                text("select geo from attendance_records where employee_id=:e"),
                {"e": ready["employee"]},
            )
        ).scalar_one()
        audits = (
            (
                await c.execute(
                    text(
                        "select after from audit_events where action like 'attendance.clock%' and company_id=:company"
                    ),
                    {"company": ready["a"]},
                )
            )
            .scalars()
            .all()
        )
    assert row["in"]["latitude"] == geo["latitude"]
    assert "out" not in row
    assert "latitude" not in json.dumps(audits)


async def test_clock_existing_record_and_employment_guards(
    ready: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    me = await linked(ready, "employee", ready["employee"])
    at(monkeypatch, "2024-12-31T09:00:00+00:00")
    assert (await me.post(API + "/clock-in", json={})).status_code == 409
    at(monkeypatch, "2026-01-05T09:00:00+00:00")
    assert (await put(ready)).status_code == 200
    assert (await me.post(API + "/clock-in", json={})).status_code == 409
    assert (
        await me.post(API + "/clock-out", json={"record_id": str(uuid.uuid4())})
    ).status_code == 404


async def test_timesheets_reports_only_no_self_stale_and_changed_approval(
    ready: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = await manager_for(ready)
    at(monkeypatch, "2026-01-12T09:00:00+00:00")
    assert (await put(ready)).status_code == 200
    page = await manager.get(API + "/timesheets?start=2026-01-07")
    assert page.status_code == 200, page.text
    assert len(page.json()["items"]) == 1
    sheet = page.json()["items"][0]
    assert sheet["period_start"] == "2026-01-05"
    assert sheet["hours"] == "7.50"
    async with ready["owner"].connect() as c:
        assert (await c.execute(text("select count(*) from timesheet_approvals"))).scalar_one() == 0
    body = {k: sheet[k] for k in ("employee_id", "period_start", "fingerprint")}
    path = API + f"/timesheets/{sheet['id']}/approve"
    unlinked = await ready["person"]("people_manager", ready["a"])
    assert (await unlinked.post(path, json=body)).status_code == 404
    own = {**body, "employee_id": str(ready["other"])}
    assert (await manager.post(path, json=own)).status_code == 403
    foreign = await ready["person"]("company_admin", ready["b"])
    assert (await foreign.post(path, json=body)).status_code == 404
    assert (await put(ready, clock_out="18:00")).status_code == 200
    assert (await manager.post(path, json=body)).status_code == 409
    current = (await manager.get(API + "/timesheets?start=2026-01-05")).json()["items"][0]
    body["fingerprint"] = current["fingerprint"]
    at(monkeypatch, "2026-01-11T23:00:00+00:00")
    assert (await manager.post(path, json=body)).status_code == 409
    at(monkeypatch, "2026-01-12T09:00:00+00:00")
    first, retry = await asyncio.gather(*[manager.post(path, json=body) for _ in range(2)])
    assert first.status_code == retry.status_code == 200, (first.text, retry.text)
    assert first.json()["approved_at"] is not None
    assert (await put(ready, note="Reviewed note changed")).status_code == 200
    assert (await manager.get(API + "/timesheets?start=2026-01-05")).json()["items"][0][
        "approved_at"
    ] is None
    async with ready["owner"].connect() as c:
        assert (
            await c.execute(
                text(
                    "select count(*) from audit_events where action='attendance.timesheet_approved'"
                )
            )
        ).scalar_one() == 1
    me = await linked(ready, "employee", ready["employee"])
    assert (await me.get(API + "/timesheets?start=2026-01-05")).status_code == 403


async def test_timesheet_incomplete_and_clock_audit_rollback(
    ready: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = await manager_for(ready)
    at(monkeypatch, "2026-01-05T09:00:00+00:00")
    me = await linked(ready, "employee", ready["employee"])
    assert (await me.post(API + "/clock-in", json={})).status_code == 200
    at(monkeypatch, "2026-01-12T09:00:00+00:00")
    sheet = (await manager.get(API + "/timesheets?start=2026-01-05")).json()["items"][0]
    assert sheet["incomplete"] is True
    assert (
        await manager.post(
            API + f"/timesheets/{sheet['id']}/approve",
            json={k: sheet[k] for k in ("employee_id", "period_start", "fingerprint")},
        )
    ).status_code == 409

    async def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(Access, "audit", fail)
    at(monkeypatch, "2026-01-05T17:00:00+00:00")
    response = await me.post(API + "/clock-out", json={"record_id": sheet["records"][0]["id"]})
    assert response.status_code == 500
    async with ready["owner"].connect() as c:
        assert (
            await c.execute(text("select clock_out from attendance_records"))
        ).scalar_one() is None
