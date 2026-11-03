"""T8.3 API scenarios: exact durations, scoped decisions and transactional side effects."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import date
from typing import Any

import httpx
import pytest
from sqlalchemy import text

from app.core.crypto import decrypt
from app.core.rbac_matrix import ROLES, Scope, scope_for
from app.modules.email.outbox import PAYLOAD_CONTEXT
from tests.db.test_compliance_hub import rig as rig
from tests.db.test_leave_settings import seeded as seeded
from tests.db.test_reminders import _keys as _keys

BASE = "/api/v1/leave"


@pytest.fixture
async def ready(seeded: dict[str, Any]) -> dict[str, Any]:
    ids = [uuid.uuid4() for _ in range(3)]
    async with seeded["owner"].begin() as c:
        await c.execute(text("delete from email_outbox"))
        await c.execute(text("delete from bank_holidays"))
        for company in (seeded["a"], seeded["b"]):
            await c.execute(
                text(
                    "insert into working_pattern_days (company_id,weekday,is_working,hours) select :c,d,d<=5,case when d<=5 then 8 else 0 end from generate_series(1,7) d"
                ),
                {"c": company},
            )
        for i, (company, ident) in enumerate(
            zip((seeded["a"], seeded["a"], seeded["b"]), ids, strict=True)
        ):
            await c.execute(
                text(
                    "insert into employees (id,company_id,employee_number,first_name,last_name,email,hire_date) values (:i,:c,:n,'Amira','Test','employee@example.com','2025-01-01')"
                ),
                {"i": ident, "c": company, "n": f"E{i}"},
            )
        await c.execute(
            text(
                "insert into bank_holidays (region,on_date,title,source) values ('england-and-wales','2026-01-01','New Year','https://www.gov.uk/bank-holidays'),('england-and-wales','2026-04-03','Good Friday','https://www.gov.uk/bank-holidays'),('england-and-wales','2027-01-01','New Year','https://www.gov.uk/bank-holidays')"
            )
        )
    admin = await seeded["person"]("company_admin", seeded["a"])
    types = (await admin.get(BASE + "/types")).json()
    return {
        **seeded,
        "admin": admin,
        "employee": ids[0],
        "other": ids[1],
        "foreign": ids[2],
        "annual": next(t["id"] for t in types if t["seed_key"] == "annual"),
        "sick": next(t["id"] for t in types if t["seed_key"] == "sick"),
    }


def payload(
    ready: dict[str, Any], *, start: str = "2026-01-05", end: str = "2026-01-09"
) -> dict[str, Any]:
    return {
        "employee_id": str(ready["employee"]),
        "leave_type_id": ready["annual"],
        "start_date": start,
        "end_date": end,
    }


async def linked(ready: dict[str, Any], role: str, employee: uuid.UUID) -> httpx.AsyncClient:
    client: httpx.AsyncClient = await ready["person"](role, ready["a"])
    user = (await client.get("/api/v1/auth/me")).json()["user"]["id"]
    async with ready["owner"].begin() as c:
        await c.execute(
            text("update memberships set employee_id=:e where user_id=:u and company_id=:c"),
            {"e": employee, "u": uuid.UUID(user), "c": ready["a"]},
        )
    return client


async def submit(ready: dict[str, Any], **kwargs: str) -> dict[str, Any]:
    response = await ready["admin"].post(BASE + "/requests", json=payload(ready, **kwargs))
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


async def counts(ready: dict[str, Any]) -> tuple[int, ...]:
    async with ready["owner"].connect() as c:
        result = [
            int((await c.execute(text(sql))).scalar_one())
            for sql in (
                "select count(*) from leave_ledger",
                "select count(*) from attendance_records",
                "select count(*) from email_outbox",
            )
        ]
        return tuple(result)


async def test_own_request_approval_books_and_notifies_without_health_details(
    ready: dict[str, Any],
) -> None:
    me = await linked(ready, "employee", ready["employee"])
    body = payload(ready)
    body.pop("employee_id")
    body["note"] = "private medical detail"
    response = await me.post(BASE + "/requests/own", json=body)
    assert response.status_code == 201, response.text
    row = response.json()
    assert (row["status"], row["working_days"]) == ("pending", "5.00")
    assert await counts(ready) == (0, 0, 0)
    assert len((await me.get(BASE + "/requests/own")).json()) == 1
    assert len((await ready["admin"].get(BASE + "/approvals/own")).json()) == 1
    decided = await ready["admin"].post(
        BASE + f"/requests/{row['id']}/approve", json={"note": "Approved"}
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "approved"
    assert await counts(ready) == (3, 5, 1)  # standard grant, bank reserve and taken
    async with ready["owner"].connect() as c:
        movements = (
            await c.execute(text("select entry_type,days from leave_ledger order by created_at,id"))
        ).all()
        assert movements == [("grant", 28), ("adjustment", -2), ("taken", -5)]
        assert set(
            (await c.execute(text("select status,source from attendance_records"))).all()
        ) == {("on_leave", "leave_sync")}
        email = (
            await c.execute(text("select to_address,template,payload from email_outbox"))
        ).one()
        data = json.loads(decrypt(email[2], context=PAYLOAD_CONTEXT))
        assert email[1] == "leave_decision"
        assert "private medical detail" not in json.dumps(data)
        assert "leave_type" not in data
        audit = (
            await c.execute(
                text("select after from audit_events where action='leave.request_approved'")
            )
        ).scalar_one()
        assert audit["status"] == "approved"
    notices = (await me.get("/api/v1/notifications")).json()
    assert "leave.decision" in json.dumps(notices)
    again = await ready["admin"].post(BASE + f"/requests/{row['id']}/approve", json={})
    assert again.status_code == 409
    assert await counts(ready) == (3, 5, 1)


async def test_counter_personal_pattern_half_days_and_closures(ready: dict[str, Any]) -> None:
    async with ready["owner"].begin() as c:
        await c.execute(
            text(
                "insert into employee_assignments (company_id,employee_id,employment_type,custom_working_days,hours_per_day,effective_from) values (:c,:e,'part_time','[\"mon\",\"wed\",\"fri\"]',4,'2025-01-01')"
            ),
            {"c": ready["a"], "e": ready["employee"]},
        )
        await c.execute(
            text(
                "insert into company_holidays (company_id,name,start_date,end_date) values (:c,'Free closure','2026-01-07','2026-01-07')"
            ),
            {"c": ready["a"]},
        )
    body = {**payload(ready), "half_day_start": True}
    result = await ready["admin"].post(BASE + "/requests/preview", json=body)
    assert result.status_code == 200, result.text
    assert result.json()["working_days"] == "0.75"
    assert result.json()["working_dates"] == ["2026-01-05", "2026-01-09"]
    made = await ready["admin"].post(BASE + "/requests", json=body)
    approved = await ready["admin"].post(BASE + f"/requests/{made.json()['id']}/approve", json={})
    assert approved.status_code == 200, approved.text
    async with ready["owner"].connect() as c:
        assert (
            await c.execute(text("select date,status from attendance_records order by date"))
        ).all() == [
            (date.fromisoformat("2026-01-05"), "half_day"),
            (date.fromisoformat("2026-01-09"), "on_leave"),
        ]


@pytest.mark.parametrize(
    ("start", "end", "half_start", "half_end"),
    [
        ("2026-01-10", "2026-01-11", False, False),
        ("2026-01-01", "2026-01-01", False, False),
        ("2026-01-05", "2026-01-05", True, True),
        ("2026-01-10", "2026-01-12", True, False),
        ("2024-12-31", "2025-01-02", False, False),
    ],
)
async def test_invalid_or_nonworking_dates(
    ready: dict[str, Any], start: str, end: str, half_start: bool, half_end: bool
) -> None:
    result = await ready["admin"].post(
        BASE + "/requests/preview",
        json={
            **payload(ready, start=start, end=end),
            "half_day_start": half_start,
            "half_day_end": half_end,
        },
    )
    assert result.status_code == 422, result.text


async def test_reject_and_cancel_leave_ledger_and_attendance_untouched(
    ready: dict[str, Any],
) -> None:
    me = await linked(ready, "employee", ready["employee"])
    row = await submit(ready)
    denied = await ready["admin"].post(
        BASE + f"/requests/{row['id']}/reject", json={"note": "Coverage"}
    )
    assert denied.status_code == 200, denied.text
    assert await counts(ready) == (0, 0, 1)
    row = await submit(ready)
    cancelled = await me.post(BASE + f"/requests/{row['id']}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert await counts(ready) == (0, 0, 1)


async def test_self_approval_forbidden_for_company_admin(ready: dict[str, Any]) -> None:
    admin = await linked(ready, "company_admin", ready["employee"])
    row = await submit(ready)
    for action in ("approve", "reject"):
        response = await admin.post(BASE + f"/requests/{row['id']}/{action}", json={})
        assert response.status_code == 403, response.text
    assert (await admin.get(BASE + "/approvals/own")).json() == []
    assert await counts(ready) == (0, 0, 0)


async def test_lsa_chain_not_reporting_chain_controls_approval(ready: dict[str, Any]) -> None:
    manager = await linked(ready, "people_manager", ready["other"])
    line = await ready["person"]("people_manager", ready["a"])
    line_id = uuid.uuid4()
    user = (await line.get("/api/v1/auth/me")).json()["user"]["id"]
    async with ready["owner"].begin() as c:
        await c.execute(
            text(
                "insert into employees (id,company_id,employee_number,first_name,last_name,email,hire_date) values (:i,:c,'M1','Line','Manager','m@example.com','2025-01-01')"
            ),
            {"i": line_id, "c": ready["a"]},
        )
        await c.execute(
            text("update memberships set employee_id=:e where user_id=:u"),
            {"e": line_id, "u": uuid.UUID(user)},
        )
        await c.execute(
            text(
                "insert into employee_assignments (company_id,employee_id,employment_type,effective_from,leave_sanctioning_employee_id,reporting_authority_employee_id) values (:c,:e,'full_time','2025-01-01',:lsa,:line)"
            ),
            {"c": ready["a"], "e": ready["employee"], "lsa": ready["other"], "line": line_id},
        )
    row = await submit(ready)
    assert len((await manager.get(BASE + "/approvals/own")).json()) == 1
    assert (await line.get(BASE + "/approvals/own")).json() == []
    assert (await line.post(BASE + f"/requests/{row['id']}/approve", json={})).status_code == 404
    preview = await manager.get(BASE + f"/approvals/{row['id']}/preview")
    assert preview.status_code == 200, preview.text
    response = await manager.post(BASE + f"/requests/{row['id']}/approve", json={})
    assert response.status_code == 200, response.text


async def test_foreign_employee_type_request_ids_and_own_access_are_hidden(
    ready: dict[str, Any],
) -> None:
    me = await linked(ready, "employee", ready["employee"])
    foreign = await ready["person"]("company_admin", ready["b"])
    foreign_type = (await foreign.get(BASE + "/types")).json()[0]["id"]
    for updates in ({"employee_id": str(ready["foreign"])}, {"leave_type_id": foreign_type}):
        response = await ready["admin"].post(BASE + "/requests", json={**payload(ready), **updates})
        assert response.status_code == 404, response.text
    assert (
        await me.post(
            BASE + "/requests", json={**payload(ready), "employee_id": str(ready["other"])}
        )
    ).status_code == 404
    row = await submit(ready)
    for action in ("approve", "reject", "cancel"):
        response = await foreign.post(
            BASE + f"/requests/{row['id']}/{action}", json={} if action != "cancel" else None
        )
        assert response.status_code == 404, response.text
    other = await linked(ready, "employee", ready["other"])
    assert (await other.get(BASE + "/requests")).json() == []
    assert (await other.post(BASE + f"/requests/{row['id']}/cancel")).status_code == 404


@pytest.mark.parametrize("role", ROLES)
async def test_request_permissions_match_matrix(ready: dict[str, Any], role: str) -> None:
    actor = await ready["person"](role, ready["a"])
    created = await actor.post(BASE + "/requests", json=payload(ready))
    scope = scope_for(role, "leave.request.create")
    expected = 403 if scope is None else 404 if scope is Scope.OWN else 201
    assert created.status_code == expected, created.text
    listing = await actor.get(BASE + "/requests")
    assert listing.status_code == (
        200 if scope_for(role, "leave.request.read") is not None else 403
    )
    approvals = await actor.get(BASE + "/approvals/own")
    assert approvals.status_code == (
        200 if scope_for(role, "leave.request.approve") is not None else 403
    )


async def test_existing_attendance_and_pattern_changes_block_booking(ready: dict[str, Any]) -> None:
    row = await submit(ready)
    async with ready["owner"].begin() as c:
        await c.execute(
            text(
                "insert into attendance_records (company_id,employee_id,date,status) values (:c,:e,'2026-01-05','present')"
            ),
            {"c": ready["a"], "e": ready["employee"]},
        )
    response = await ready["admin"].post(BASE + f"/requests/{row['id']}/approve", json={})
    assert response.status_code == 409, response.text
    assert await counts(ready) == (0, 1, 0)
    async with ready["owner"].begin() as c:
        await c.execute(text("delete from attendance_records"))
        await c.execute(
            text(
                "insert into employee_assignments (company_id,employee_id,employment_type,hours_per_day,effective_from) values (:c,:e,'part_time',4,'2025-01-01')"
            ),
            {"c": ready["a"], "e": ready["employee"]},
        )
    changed = await ready["admin"].post(BASE + f"/requests/{row['id']}/approve", json={})
    assert changed.status_code == 409, changed.text
    assert await counts(ready) == (0, 0, 0)


async def test_overlap_and_concurrent_decisions_never_double_book(ready: dict[str, Any]) -> None:
    row = await submit(ready)
    overlap = await ready["admin"].post(BASE + "/requests", json=payload(ready))
    assert overlap.status_code == 409
    results = await asyncio.gather(
        *(ready["admin"].post(BASE + f"/requests/{row['id']}/approve", json={}) for _ in range(2))
    )
    assert sorted(r.status_code for r in results) == [200, 409]
    assert await counts(ready) == (3, 5, 0)


async def test_failed_audit_rolls_back_balance_attendance_and_email(
    ready: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    await linked(ready, "employee", ready["employee"])
    row = await submit(ready)

    async def broken(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr("app.modules.rbac.deps.record_audit", broken)
    response = await ready["admin"].post(BASE + f"/requests/{row['id']}/approve", json={})
    assert response.status_code == 500
    assert await counts(ready) == (0, 0, 0)
    assert (await ready["admin"].get(BASE + "/requests")).json()[0]["status"] == "pending"


async def test_year_boundary_splits_taken_movements_and_excludes_bank_day(
    ready: dict[str, Any],
) -> None:
    row = await submit(ready, start="2026-12-31", end="2027-01-04")
    assert row["working_days"] == "2.00"
    response = await ready["admin"].post(BASE + f"/requests/{row['id']}/approve", json={})
    assert response.status_code == 200, response.text
    async with ready["owner"].connect() as c:
        assert (
            await c.execute(
                text(
                    "select leave_year_start,days from leave_ledger where entry_type='taken' order by leave_year_start"
                )
            )
        ).all() == [(date.fromisoformat("2026-01-01"), -1), (date.fromisoformat("2027-01-01"), -1)]


async def test_negative_balance_policy_and_no_fixed_allowance(ready: dict[str, Any]) -> None:
    async with ready["owner"].begin() as c:
        await c.execute(
            text("update leave_types set days_per_year=0 where id=:t"),
            {"t": uuid.UUID(ready["annual"])},
        )
    row = await submit(ready)
    response = await ready["admin"].post(BASE + f"/requests/{row['id']}/approve", json={})
    assert response.status_code == 409, response.text
    assert await counts(ready) == (0, 0, 0)
    await ready["admin"].post(BASE + f"/requests/{row['id']}/cancel")
    made = await ready["admin"].post(
        BASE + "/requests", json={**payload(ready), "leave_type_id": ready["sick"]}
    )
    approved = await ready["admin"].post(BASE + f"/requests/{made.json()['id']}/approve", json={})
    assert approved.status_code == 200, approved.text
    assert await counts(ready) == (1, 5, 0)


async def test_configured_no_approval_policy_books_automatically(ready: dict[str, Any]) -> None:
    me = await linked(ready, "employee", ready["employee"])
    async with ready["owner"].begin() as c:
        await c.execute(
            text("update leave_types set requires_approval=false where id=:t"),
            {"t": uuid.UUID(ready["annual"])},
        )
    body = payload(ready)
    body.pop("employee_id")
    response = await me.post(BASE + "/requests/own", json=body)
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "approved"
    assert response.json()["decided_by"] is None
    assert await counts(ready) == (3, 5, 1)


async def test_team_overlap_and_empty_department_are_advisory(ready: dict[str, Any]) -> None:
    department = uuid.uuid4()
    async with ready["owner"].begin() as c:
        await c.execute(
            text("insert into departments (id,company_id,name) values (:d,:c,'Care team')"),
            {"d": department, "c": ready["a"]},
        )
        for employee in (ready["employee"], ready["other"]):
            await c.execute(
                text(
                    "insert into employee_assignments (company_id,employee_id,employment_type,effective_from,department_id) values (:c,:e,'full_time','2025-01-01',:d)"
                ),
                {"c": ready["a"], "e": employee, "d": department},
            )
    await submit(ready)
    response = await ready["admin"].post(
        BASE + "/requests/preview", json={**payload(ready), "employee_id": str(ready["other"])}
    )
    assert response.status_code == 200, response.text
    warnings = response.json()["conflicts"]
    assert {w["code"] for w in warnings} == {"TEAM_OVERLAP", "MINIMUM_STAFFING"}
    assert all(not w["blocking"] for w in warnings)


async def test_missing_calendar_and_negative_policy_enabled(ready: dict[str, Any]) -> None:
    unavailable = await ready["admin"].post(
        BASE + "/requests/preview", json=payload(ready, start="2028-01-04", end="2028-01-04")
    )
    assert unavailable.status_code == 503
    async with ready["owner"].begin() as c:
        await c.execute(
            text("update companies set allow_negative_leave_balance=true where id=:c"),
            {"c": ready["a"]},
        )
        await c.execute(
            text("update leave_types set days_per_year=0 where id=:t"),
            {"t": uuid.UUID(ready["annual"])},
        )
    row = await submit(ready)
    approver = await ready["person"]("hr_admin", ready["a"])
    approved = await approver.post(BASE + f"/requests/{row['id']}/approve", json={})
    assert approved.status_code == 200, approved.text
    async with ready["owner"].connect() as c:
        assert (await c.execute(text("select sum(days) from leave_ledger"))).scalar_one() == -7
