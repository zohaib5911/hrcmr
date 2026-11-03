"""T9.1 scoped manual records, exact clock math, summary and atomic protections."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from sqlalchemy import text

from tests.db.test_compliance_hub import rig as rig
from tests.db.test_leave_requests import BASE, linked, submit
from tests.db.test_leave_requests import ready as ready
from tests.db.test_leave_settings import seeded as seeded
from tests.db.test_reminders import _keys as _keys

API = "/api/v1/attendance-records"


def body(ready: dict[str, Any], **values: Any) -> dict[str, Any]:
    return {
        "employee_id": str(ready["employee"]),
        "date": "2026-01-05",
        "status": "present",
        "clock_in": "09:00",
        "clock_out": "17:00",
        "unpaid_break_minutes": 30,
        **values,
    }


async def put(ready: dict[str, Any], **values: Any) -> Any:
    return await ready["admin"].put(API, json=body(ready, **values))


async def test_upsert_summary_range_filters_and_audit_without_private_note(
    ready: dict[str, Any],
) -> None:
    first = await put(ready, note="Private health detail")
    assert first.status_code == 200, first.text
    assert first.json()["hours"] == "7.50"
    assert first.json()["source"] == "manual"
    changed = await put(ready, status="late", clock_in="09:30", note="Updated private detail")
    assert changed.status_code == 200, changed.text
    assert changed.json()["id"] == first.json()["id"]
    assert changed.json()["hours"] == "7.00"
    second = await put(
        ready,
        employee_id=str(ready["other"]),
        status="sick",
        clock_in=None,
        clock_out=None,
        unpaid_break_minutes=0,
    )
    assert second.status_code == 200, second.text
    summary = await ready["admin"].get(API + "/summary?on=2026-01-05")
    assert summary.status_code == 200, summary.text
    assert summary.json()["employees"] == 2
    assert summary.json()["counts"]["late"] == 1
    assert summary.json()["counts"]["sick"] == 1
    assert summary.json()["not_recorded"] == 0
    listed = await ready["admin"].get(API + "?start=2026-01-01&end=2026-01-31&limit=1")
    assert listed.json()["total"] == 2
    assert listed.json()["next_offset"] == 1
    filtered = await ready["admin"].get(API + "?start=2026-01-01&end=2026-01-31&status=late")
    assert len(filtered.json()["items"]) == 1
    assert filtered.json()["items"][0]["employee_name"] == "Amira Test"
    async with ready["owner"].connect() as c:
        audits = (
            (
                await c.execute(
                    text(
                        "select after from audit_events where action like 'attendance.%' and company_id=:c"
                    ),
                    {"c": ready["a"]},
                )
            )
            .scalars()
            .all()
        )
        assert len(audits) == 3
        assert "Private health detail" not in json.dumps(audits)
        assert "Updated private detail" not in json.dumps(audits)
        assert audits[0]["note_changed"] is True


@pytest.mark.parametrize(
    ("day", "start", "end", "expected"),
    [
        ("2026-01-05", "22:00", "06:00", "8.00"),
        ("2026-03-29", "00:30", "02:30", "1.00"),
        ("2026-10-25", "00:30", "02:30", "3.00"),
    ],
)
async def test_overnight_and_company_zone_clock_changes(
    ready: dict[str, Any], day: str, start: str, end: str, expected: str
) -> None:
    response = await put(ready, date=day, clock_in=start, clock_out=end, unpaid_break_minutes=0)
    assert response.status_code == 200, response.text
    assert response.json()["hours"] == expected
    assert response.json()["clock_in_local"] == start
    assert response.json()["clock_out_local"] == end


async def test_repeated_hour_requires_review_and_nonexistent_time_fails(
    ready: dict[str, Any],
) -> None:
    response = await put(
        ready, date="2026-10-25", clock_in="01:30", clock_out="03:00", unpaid_break_minutes=0
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "AMBIGUOUS_LOCAL_TIME"
    response = await put(
        ready,
        date="2026-10-25",
        clock_in="01:30",
        clock_out="03:00",
        clock_in_fold=1,
        unpaid_break_minutes=0,
    )
    assert response.status_code == 200, response.text
    assert response.json()["hours"] == "1.50"
    assert response.json()["clock_in_fold"] == 1
    response = await put(ready, date="2026-03-29", clock_in="01:30", clock_out="03:00")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_LOCAL_TIME"


@pytest.mark.parametrize(
    "changes",
    [
        {"clock_out": None},
        {"unpaid_break_minutes": 600},
        {"status": "absent"},
        {"date": "2024-12-31"},
        {"clock_in": "09:00:01"},
        {"clock_in": "09:00+01:00"},
    ],
)
async def test_invalid_manual_inputs(ready: dict[str, Any], changes: dict[str, Any]) -> None:
    response = await put(ready, **changes)
    assert response.status_code == 422, response.text


async def test_own_scope_foreign_company_and_clock_only_write_permission(
    ready: dict[str, Any],
) -> None:
    assert (await put(ready)).status_code == 200
    assert (await put(ready, employee_id=str(ready["other"]))).status_code == 200
    me = await linked(ready, "employee", ready["employee"])
    for url in (API, API + "/own"):
        response = await me.get(url + "?start=2026-01-01&end=2026-01-31")
        assert response.status_code == 200, response.text
        assert {r["employee_id"] for r in response.json()["items"]} == {str(ready["employee"])}
    assert (await me.put(API, json=body(ready))).status_code == 403
    assert (
        await me.get(API + f"?start=2026-01-01&end=2026-01-31&employee_id={ready['other']}")
    ).status_code == 404
    foreign = await ready["person"]("company_admin", ready["b"])
    response = await foreign.get(API + "?start=2026-01-01&end=2026-01-31")
    assert response.json()["items"] == []
    assert (await foreign.put(API, json=body(ready))).status_code == 404
    manager = await ready["person"]("people_manager", ready["a"])
    assert (await manager.get(API + "?start=2026-01-01&end=2026-01-31")).json()["total"] == 2
    assert (await manager.put(API, json=body(ready))).status_code == 403


async def test_leave_sync_is_protected_and_upserts_serialize(ready: dict[str, Any]) -> None:
    row = await submit(ready)
    assert (
        await ready["admin"].post(BASE + f"/requests/{row['id']}/approve", json={})
    ).status_code == 200
    assert (await put(ready)).status_code == 409
    replies = await asyncio.gather(*(put(ready, date="2026-01-12") for _ in range(2)))
    assert [r.status_code for r in replies] == [200, 200]
    assert replies[0].json()["id"] == replies[1].json()["id"]
    async with ready["owner"].connect() as c:
        assert (
            await c.execute(text("select count(*) from attendance_records where date='2026-01-12'"))
        ).scalar_one() == 1
        assert (
            await c.execute(
                text("select count(*) from attendance_records where source='leave_sync'")
            )
        ).scalar_one() == 5


async def test_failed_audit_rolls_back(
    ready: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr("app.modules.rbac.deps.record_audit", broken)
    response = await put(ready)
    assert response.status_code == 500
    async with ready["owner"].connect() as c:
        assert (await c.execute(text("select count(*) from attendance_records"))).scalar_one() == 0
