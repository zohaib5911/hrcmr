"""T9.5 optimistic scoped shifts, UTC/local overnight hours and warning projections."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text

from app.modules.rbac.deps import Access
from tests.db.test_attendance_clock import manager_for
from tests.db.test_compliance_hub import rig as rig
from tests.db.test_leave_requests import BASE, submit
from tests.db.test_leave_requests import ready as ready
from tests.db.test_leave_settings import seeded as seeded
from tests.db.test_reminders import _keys as _keys

API = "/api/v1/rota"


def payload(ready: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return {
        "employee_id": str(ready["employee"]),
        "date": "2026-01-05",
        "starts_at": "09:00",
        "ends_at": "17:00",
        "version": 0,
        **changes,
    }


async def test_grid_read_only_versioned_crud_overlap_and_overnight(ready: dict[str, Any]) -> None:
    admin = ready["admin"]
    empty = await admin.get(API + "/weeks/2026-01-05?limit=1")
    assert empty.status_code == 200, empty.text
    assert empty.json()["version"] == 0
    assert empty.json()["next_offset"] == 1
    async with ready["owner"].connect() as c:
        assert (await c.execute(text("select count(*) from rota_weeks"))).scalar_one() == 0
    response = await admin.post(API + "/scheduled-shifts", json=payload(ready))
    assert response.status_code == 201, response.text
    assert response.json()["shift"]["hours"] == "8.00"
    ident = response.json()["shift"]["id"]
    assert (
        await admin.post(API + "/scheduled-shifts", json=payload(ready, date="2026-01-06"))
    ).status_code == 409
    assert (
        await admin.post(
            API + "/scheduled-shifts", json=payload(ready, starts_at="10:00", version=1)
        )
    ).status_code == 409
    updated = await admin.put(
        API + f"/scheduled-shifts/{ident}",
        json=payload(ready, starts_at="22:00", ends_at="06:00", unpaid_break_minutes=30, version=1),
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["shift"]["hours"] == "7.50"
    grid = (await admin.get(API + "/weeks/2026-01-05")).json()
    assert grid["totals"]["2026-01-05"] == "7.50"
    assert len(grid["not_scheduled"]) == 1
    assert (await admin.delete(API + f"/scheduled-shifts/{ident}?version=1")).status_code == 409
    assert (await admin.delete(API + f"/scheduled-shifts/{ident}?version=2")).status_code == 200
    assert (await admin.get(API + "/weeks/2026-01-05")).json()["shifts"] == []


async def test_report_writes_foreign_ids_and_employment_dates(ready: dict[str, Any]) -> None:
    manager = await manager_for(ready)
    response = await manager.post(API + "/scheduled-shifts", json=payload(ready))
    assert response.status_code == 201, response.text
    for employee in (ready["other"], ready["foreign"]):
        assert (
            await manager.post(
                API + "/scheduled-shifts",
                json=payload(ready, employee_id=str(employee), date="2026-01-06", version=1),
            )
        ).status_code == 404
    foreign = await ready["person"]("company_admin", ready["b"])
    assert (await foreign.get(API + "/weeks/2026-01-05")).json()["shifts"] == []
    ident = response.json()["shift"]["id"]
    assert (
        await foreign.put(API + f"/scheduled-shifts/{ident}", json=payload(ready))
    ).status_code == 404
    assert (await foreign.delete(API + f"/scheduled-shifts/{ident}?version=1")).status_code == 404
    assert (
        await ready["admin"].post(API + "/scheduled-shifts", json=payload(ready, date="2024-12-30"))
    ).status_code == 422
    assert (await ready["admin"].get(API + "/weeks/2026-01-06")).status_code == 422


async def test_warnings_leave_holiday_weekly_hours_rest_and_optout(ready: dict[str, Any]) -> None:
    admin = ready["admin"]
    request = await submit(ready, start="2026-01-05", end="2026-01-05")
    assert (
        await admin.post(BASE + f"/requests/{request['id']}/approve", json={})
    ).status_code == 200
    async with ready["owner"].begin() as c:
        await c.execute(
            text(
                "insert into company_holidays (company_id,name,start_date,end_date) values (:c,'Closure','2026-01-05','2026-01-05')"
            ),
            {"c": ready["a"]},
        )
    for i in range(7):
        response = await admin.post(
            API + "/scheduled-shifts",
            json=payload(
                ready,
                date=f"2026-01-{5 + i:02d}",
                starts_at="06:00" if i == 1 else "09:00",
                ends_at="17:00",
                version=i,
            ),
        )
        assert response.status_code == 201, response.text
    grid = (await admin.get(API + "/weeks/2026-01-05")).json()
    codes = {w["code"] for w in grid["warnings"]}
    assert {"APPROVED_LEAVE", "COMPANY_HOLIDAY", "WEEKLY_HOURS"} <= codes
    # Replace Monday with overnight hours; Tuesday starts at 06:00, giving no rest.
    first = next(s for s in grid["shifts"] if s["date"] == "2026-01-05")
    assert (
        await admin.put(
            API + f"/scheduled-shifts/{first['id']}",
            json=payload(ready, starts_at="22:00", ends_at="06:00", version=7),
        )
    ).status_code == 200
    assert "REST" in {
        w["code"] for w in (await admin.get(API + "/weeks/2026-01-05")).json()["warnings"]
    }
    async with ready["owner"].begin() as c:
        await c.execute(
            text("update employees set opted_out_48h_week=true where id=:e"),
            {"e": ready["employee"]},
        )
    assert "WEEKLY_HOURS" not in {
        w["code"] for w in (await admin.get(API + "/weeks/2026-01-05")).json()["warnings"]
    }


async def test_repeated_hours_and_audit_rollback(
    ready: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = ready["admin"]
    body = payload(ready, date="2026-10-25", starts_at="01:30", ends_at="03:00")
    assert (await admin.post(API + "/scheduled-shifts", json=body)).status_code == 422
    response = await admin.post(API + "/scheduled-shifts", json={**body, "starts_fold": 1})
    assert response.status_code == 201, response.text
    assert response.json()["shift"]["hours"] == "1.50"

    async def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("audit failed")

    monkeypatch.setattr(Access, "audit", fail)
    assert (await admin.post(API + "/scheduled-shifts", json=payload(ready))).status_code == 500
    async with ready["owner"].connect() as c:
        assert (
            await c.execute(text("select count(*) from scheduled_shifts where date='2026-01-05'"))
        ).scalar_one() == 0
        assert (
            await c.execute(text("select count(*) from rota_weeks where week_start='2026-01-05'"))
        ).scalar_one() == 0


async def test_atomic_copy_clear_actions_and_report_scope(ready: dict[str, Any]) -> None:
    admin = ready["admin"]
    manager = await manager_for(ready)
    assert (await admin.post(API + "/scheduled-shifts", json=payload(ready))).status_code == 201
    copied = await admin.post(
        API + "/weeks/2026-01-05/copy-day",
        json={"version": 1, "source": "2026-01-05", "targets": ["2026-01-06", "2026-01-07"]},
    )
    assert copied.status_code == 200, copied.text
    assert copied.json() == {"count": 2, "version": 2}
    assert (
        await admin.post(API + "/weeks/2026-01-05/clear", json={"version": 1})
    ).status_code == 409
    assert (
        await admin.post(
            API + "/weeks/2026-01-05/copy-day",
            json={"version": 2, "source": "2026-01-05", "targets": ["2026-01-05"]},
        )
    ).status_code == 422
    assert (
        await admin.post(API + "/weeks/2026-01-05/clear", json={"version": 2, "on": "2026-01-06"})
    ).json() == {"count": 1, "version": 3}
    copied = await admin.post(API + "/weeks/2026-01-12/copy-last-week", json={"version": 0})
    assert copied.status_code == 200, copied.text
    assert copied.json()["count"] == 2
    assert (
        await admin.post(
            API + "/weeks/2026-01-12/clear-employee-week",
            json={"version": 1, "employee_id": str(ready["employee"])},
        )
    ).json() == {"count": 2, "version": 2}
    assert (
        await admin.post(
            API + "/scheduled-shifts",
            json=payload(ready, employee_id=str(ready["other"]), date="2026-01-09", version=3),
        )
    ).status_code == 201
    response = await manager.post(API + "/weeks/2026-01-05/clear", json={"version": 4})
    assert response.status_code == 200, response.text
    remaining = (await admin.get(API + "/weeks/2026-01-05")).json()["shifts"]
    assert len(remaining) == 1
    assert remaining[0]["employee_id"] == str(ready["other"])
    assert (
        await manager.post(
            API + "/weeks/2026-01-05/copy-employee-week",
            json={"version": 5, "employee_id": str(ready["other"])},
        )
    ).status_code == 404


async def test_copy_rollback_keeps_replaced_shifts(
    ready: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = ready["admin"]
    assert (await admin.post(API + "/scheduled-shifts", json=payload(ready))).status_code == 201
    target = await admin.post(
        API + "/scheduled-shifts",
        json=payload(ready, date="2026-01-06", starts_at="10:00", version=1),
    )
    assert target.status_code == 201
    original = target.json()["shift"]["id"]

    async def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("audit failed")

    monkeypatch.setattr(Access, "audit", fail)
    response = await admin.post(
        API + "/weeks/2026-01-05/copy-day",
        json={"version": 2, "source": "2026-01-05", "targets": ["2026-01-06"]},
    )
    assert response.status_code == 500
    current = (await admin.get(API + "/weeks/2026-01-05")).json()
    assert current["version"] == 2
    assert any(s["id"] == original and s["starts_local"] == "10:00" for s in current["shifts"])
