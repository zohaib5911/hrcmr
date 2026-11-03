"""T8.4 projections, scoped calendar and atomic adjustments."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import text

from tests.db.test_compliance_hub import rig as rig
from tests.db.test_leave_requests import BASE, linked, submit
from tests.db.test_leave_requests import ready as ready
from tests.db.test_leave_settings import seeded as seeded
from tests.db.test_reminders import _keys as _keys


def annual(response: Any, ready: dict[str, Any]) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    result: dict[str, Any] = next(
        row for row in response.json()["items"] if row["leave_type_id"] == ready["annual"]
    )
    return result


async def test_projection_pending_taken_and_no_get_writes(ready: dict[str, Any]) -> None:
    me = await linked(ready, "employee", ready["employee"])
    url = "/api/v1/leave-balances/own?on=2026-01-05"
    first = annual(await me.get(url), ready)
    assert (first["available"], first["entitlement"], first["calendar_days"]) == (
        "26.00",
        "28.00",
        "2.00",
    )
    assert first["ledger_balance"] == "0.00"
    async with ready["owner"].connect() as c:
        assert (await c.execute(text("select count(*) from leave_ledger"))).scalar_one() == 0
    row = await submit(ready)
    pending = annual(await me.get(url), ready)
    assert (pending["available"], pending["pending"]) == ("26.00", "5")
    approved = await ready["admin"].post(BASE + f"/requests/{row['id']}/approve", json={})
    assert approved.status_code == 200, approved.text
    final = annual(await me.get(url), ready)
    assert (final["available"], final["taken"], final["pending"]) == ("21.00", "5.00", "0")


async def test_scopes_pagination_and_foreign_ids(ready: dict[str, Any]) -> None:
    me = await linked(ready, "employee", ready["employee"])
    for ident in (ready["other"], ready["foreign"]):
        assert (
            await me.get(f"/api/v1/employees/{ident}/leave-balances?on=2026-01-05")
        ).status_code == 404
    assert (
        await ready["admin"].get(f"/api/v1/employees/{ready['foreign']}/leave-balances")
    ).status_code == 404
    page = await ready["admin"].get("/api/v1/leave-balances?on=2026-01-05&limit=1")
    assert page.status_code == 200, page.text
    assert page.json()["next_offset"] == 1
    second = await ready["admin"].get("/api/v1/leave-balances?on=2026-01-05&limit=1&offset=1")
    assert second.json()["next_offset"] is None
    assert page.json()["items"][0]["employee_id"] != second.json()["items"][0]["employee_id"]
    assert all(
        r["employee_id"] == str(ready["employee"])
        for r in (await me.get("/api/v1/leave-balances?on=2026-01-05")).json()["items"]
    )


async def test_grant_deduct_set_retries_reason_and_negative_policy(ready: dict[str, Any]) -> None:
    url = f"/api/v1/employees/{ready['employee']}/leave-balances"
    body = {
        "leave_type_id": ready["annual"],
        "on": "2026-01-05",
        "days": "2",
        "reason": "Reviewed allowance",
        "idempotency_key": str(uuid.uuid4()),
    }
    assert (
        annual(await ready["admin"].post(url + "/grant", json=body), ready)["available"] == "28.00"
    )
    assert (
        annual(await ready["admin"].post(url + "/grant", json=body), ready)["available"] == "28.00"
    )
    for operation, amount, expected in (("deduct", "3", "25.00"), ("set", "10", "10.00")):
        body.update(days=amount, idempotency_key=str(uuid.uuid4()))
        assert (
            annual(await ready["admin"].post(url + "/" + operation, json=body), ready)["available"]
            == expected
        )
    body.update(days="99", idempotency_key=str(uuid.uuid4()))
    assert (await ready["admin"].post(url + "/deduct", json=body)).status_code == 409
    body.update(reason="   ", days="1")
    assert (await ready["admin"].post(url + "/grant", json=body)).status_code == 422
    me = await linked(ready, "employee", ready["employee"])
    body["reason"] = "Reviewed"
    assert (await me.post(url + "/grant", json=body)).status_code == 403
    assert (
        await ready["admin"].post(
            f"/api/v1/employees/{ready['foreign']}/leave-balances/grant", json=body
        )
    ).status_code == 404
    async with ready["owner"].connect() as c:
        assert (
            await c.execute(
                text(
                    "select count(*) from leave_ledger where entry_type='grant' and bucket is null"
                )
            )
        ).scalar_one() == 1
        assert (
            await c.execute(
                text(
                    "select count(*) from audit_events where action like 'leave.balance_%' and reason='Reviewed allowance'"
                )
            )
        ).scalar_one() == 3


async def test_balance_action_audit_failure_rolls_back(
    ready: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr("app.modules.rbac.deps.record_audit", broken)
    response = await ready["admin"].post(
        f"/api/v1/employees/{ready['employee']}/leave-balances/grant",
        json={
            "leave_type_id": ready["annual"],
            "on": "2026-01-05",
            "days": "1",
            "reason": "Reviewed",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 500
    async with ready["owner"].connect() as c:
        assert (await c.execute(text("select count(*) from leave_ledger"))).scalar_one() == 0


async def test_calendar_working_dates_scope_and_department(ready: dict[str, Any]) -> None:
    await submit(ready)
    other = await linked(ready, "employee", ready["other"])
    calendar = await ready["admin"].get(BASE + "/calendar?month=2026-01")
    assert calendar.status_code == 200, calendar.text
    assert len(calendar.json()["items"]) == 1
    assert calendar.json()["items"][0]["working_dates"] == [f"2026-01-0{i}" for i in range(5, 10)]
    assert "note" not in calendar.json()["items"][0]
    assert (await other.get(BASE + "/calendar?month=2026-01")).json()["items"] == []
    assert (
        await ready["admin"].get(BASE + f"/calendar?month=2026-01&department_id={uuid.uuid4()}")
    ).json()["items"] == []
    assert (await ready["admin"].get(BASE + "/calendar?month=0000-01")).status_code == 422
