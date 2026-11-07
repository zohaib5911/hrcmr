"""T10.3 policy drafts, scoped audiences, stale previews, atomic sends and retained versions."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import text

from app.db.session import TenantSession
from app.jobs.policies import reconcile_policies
from app.modules.companies.models import Department, Location
from app.modules.employees.models import EmployeeAssignment
from app.modules.policies import service
from app.modules.sponsor_documents.models import SponsorDocument
from tests.db.test_employee_documents import _employee
from tests.db.test_employee_documents import _keys as _keys
from tests.db.test_employee_documents import rig as rig
from tests.db.test_files import PDF

API = "/api/v1/policies"


def draft(**changes: Any) -> dict[str, Any]:
    return {"title": "Staff handbook", "category": "employee_handbook", **changes}


async def document(admin: httpx.AsyncClient, **changes: Any) -> dict[str, Any]:
    made = await admin.post(API, json=draft(**changes))
    assert made.status_code == 201, made.text
    row = made.json()
    file = await admin.post(
        API + f"/{row['id']}/file", files={"file": ("handbook.pdf", PDF, "application/pdf")}
    )
    assert file.status_code == 200, file.text
    result: dict[str, Any] = file.json()
    return result


async def send(admin: httpx.AsyncClient, row: dict[str, Any]) -> httpx.Response:
    preview = await admin.get(API + f"/{row['id']}/recipients")
    assert preview.status_code == 200, preview.text
    return await admin.post(
        API + f"/{row['id']}/send", json={"preview_token": preview.json()["preview_token"]}
    )


async def linked(rig: dict[str, Any], employee: uuid.UUID) -> httpx.AsyncClient:
    member: httpx.AsyncClient = await rig["person"]("employee", rig["a"])
    async with rig["owner"].begin() as db:
        await db.execute(
            text("update memberships set employee_id=:e where company_id=:c and role='employee'"),
            {"e": employee, "c": rig["a"]},
        )
    return member


async def test_draft_upload_review_send_is_atomic_idempotent_and_notifies(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    employee = await _employee(rig, rig["a"], "POL1")
    member = await linked(rig, employee)
    async with rig["owner"].connect() as db:
        before_messages = (
            await db.execute(
                text("select count(*) from email_outbox where template='policy_request'")
            )
        ).scalar_one()
    initial = await admin.post(API, json=draft())
    assert initial.status_code == 201, initial.text
    row = initial.json()
    assert row["version"] == 1
    assert row["file_id"] is None
    preview = (await admin.get(API + f"/{row['id']}/recipients")).json()
    assert len(preview["items"]) == 1
    assert preview["items"][0]["employee_id"] == str(employee)
    assert (
        await admin.post(
            API + f"/{row['id']}/send", json={"preview_token": preview["preview_token"]}
        )
    ).status_code == 422
    uploaded = await admin.post(API + f"/{row['id']}/file", files={"file": ("handbook.pdf", PDF)})
    assert uploaded.status_code == 200, uploaded.text
    assert (
        await admin.post(
            API + f"/{row['id']}/send", json={"preview_token": preview["preview_token"]}
        )
    ).status_code == 409
    sent = await send(admin, row)
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "sent"
    assert sent.json()["recipients"] == 1
    assert (await send(admin, row)).status_code == 200
    assignments = (await admin.get(API + f"/{row['id']}/acceptances")).json()
    assert len(assignments) == 1
    assert assignments[0]["due_on"] == preview["items"][0]["due_on"]
    inbox = await member.get("/api/v1/notifications")
    assert inbox.status_code == 200, inbox.text
    assert any(
        n["kind"] == "policy.assigned" and n["link"] == f"/my-documents?policy={row['id']}"
        for n in inbox.json()["items"]
    )
    assert (
        await admin.patch(API + f"/{row['id']}", json=draft(title="Rewrite"))
    ).status_code == 409
    assert (
        await admin.post(API + f"/{row['id']}/file", files={"file": ("rewrite.pdf", PDF)})
    ).status_code == 409
    profile = (await admin.get(f"/api/v1/employees/{employee}")).json()
    assert not profile["can_delete"]
    assert "policy sign-offs" in profile["delete_blocker"]
    async with rig["owner"].connect() as db:
        messages = (
            (
                await db.execute(
                    text("select payload from email_outbox where template='policy_request'")
                )
            )
            .scalars()
            .all()
        )
        assert len(messages) == before_messages + 1
        assert "Staff handbook" not in messages[0]
        actions = set(
            (
                await db.execute(
                    text("select action from audit_events where company_id=:c"), {"c": rig["a"]}
                )
            ).scalars()
        )
    assert {"policy.created", "policy.file_uploaded", "policy.sent"} <= actions


async def test_audiences_use_current_assignments_visa_and_current_employees(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("hr_admin", rig["a"])
    a = await _employee(rig, rig["a"], "A")
    b = await _employee(rig, rig["a"], "B")
    archived = await _employee(rig, rig["a"], "ARCH")
    async with rig["owner"].begin() as db:
        await db.execute(
            text("update employees set status='archived' where id=:i"), {"i": archived}
        )
    async with TenantSession(rig["app"].state.engine, company_id=rig["a"]) as db:
        department = Department(company_id=rig["a"], name="Policy department")
        location = Location(
            company_id=rig["a"],
            name="Policy office",
            postcode="SW1A 1AA",
            address_line1="1 Test Street",
            city="London",
        )
        db.add_all([department, location])
        await db.flush()
        db.add(
            EmployeeAssignment(
                company_id=rig["a"],
                employee_id=a,
                department_id=department.id,
                location_id=location.id,
                employment_type="full_time",
                effective_from=date(2025, 1, 1),
            )
        )
        db.add(
            SponsorDocument(
                company_id=rig["a"], employee_id=b, doc_type="visa", visa_route="other", version=1
            )
        )
        await db.commit()
        department_id, location_id = department.id, location.id
    for kind, ids, expected in [
        ("everyone", [], {a, b}),
        ("named", [a], {a}),
        ("departments", [department_id], {a}),
        ("locations", [location_id], {a}),
        ("visa_holders", [], {b}),
    ]:
        made = await admin.post(
            API, json=draft(audience_type=kind, audience_ids=list(map(str, ids)))
        )
        assert made.status_code == 201, made.text
        preview = (await admin.get(API + f"/{made.json()['id']}/recipients")).json()
        assert {uuid.UUID(p["employee_id"]) for p in preview["items"]} == expected
    for changes in (
        {"audience_type": "named", "audience_ids": []},
        {"audience_ids": [str(a)]},
        {"audience_type": "named", "audience_ids": [str(a), str(a)]},
        {"title": "Policy\nheader"},
    ):
        assert (await admin.post(API, json=draft(**changes))).status_code == 422
    foreign = await _employee(rig, rig["b"], "FOREIGN")
    assert (
        await admin.post(API, json=draft(audience_type="named", audience_ids=[str(foreign)]))
    ).status_code == 422
    for kind in ("departments", "locations"):
        assert (
            await admin.post(API, json=draft(audience_type=kind, audience_ids=[str(uuid.uuid4())]))
        ).status_code == 422


async def test_preview_changes_and_pending_scan_cannot_send(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    await _employee(rig, rig["a"], "ONE")
    row = await document(admin)
    old = (await admin.get(API + f"/{row['id']}/recipients")).json()["preview_token"]
    await _employee(rig, rig["a"], "TWO")
    assert (
        await admin.post(API + f"/{row['id']}/send", json={"preview_token": old})
    ).status_code == 409
    async with rig["owner"].begin() as db:
        await db.execute(
            text("update files set scan_status='pending' where id=:i"), {"i": row["file_id"]}
        )
    assert (await send(admin, row)).status_code == 422
    assert (await admin.get(API + f"/{row['id']}")).json()["status"] == "draft"
    assert (await admin.get(API + f"/{row['id']}/acceptances")).json() == []


async def test_new_version_requires_file_and_keeps_original_assignments(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    await _employee(rig, rig["a"], "VERSION")
    first = await document(admin)
    assert (await send(admin, first)).status_code == 200
    original = (await admin.get(API + f"/{first['id']}/acceptances")).json()
    made = await admin.post(API + f"/{first['id']}/new-version")
    assert made.status_code == 201, made.text
    second = made.json()
    assert second["version"] == 2
    assert second["previous_version_id"] == first["id"]
    assert second["file_id"] is None
    assert (await admin.post(API + f"/{first['id']}/new-version")).json()["id"] == second["id"]
    assert (await send(admin, second)).status_code == 422
    assert (
        await admin.post(API + f"/{second['id']}/file", files={"file": ("version2.pdf", PDF)})
    ).status_code == 200
    assert (await send(admin, second)).status_code == 200
    assert (await admin.get(API + f"/{first['id']}")).json()["status"] == "archived"
    assert (await admin.get(API + f"/{first['id']}/acceptances")).json() == original
    assert (await admin.get(API + f"/{second['id']}")).json()["completed"] == 0
    assert (await admin.delete(API + f"/{second['id']}")).status_code == 204
    assert (await admin.delete(API + f"/{second['id']}")).status_code == 204


async def test_scope_tenant_and_demoted_uploader_file_access(rig: dict[str, Any]) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    row = await document(hr)
    foreign = await rig["person"]("company_admin", rig["b"])
    for suffix in ("", "/recipients", "/acceptances"):
        assert (await foreign.get(API + f"/{row['id']}" + suffix)).status_code == 404
    assert (await foreign.patch(API + f"/{row['id']}", json=draft())).status_code == 404
    assert (await foreign.delete(API + f"/{row['id']}")).status_code == 404
    for role in ("employee", "people_manager", "recruiter", "read_only_auditor"):
        other = await rig["person"](role, rig["a"])
        assert (await other.post(API, json=draft())).status_code == 403
        assert (await other.get(API)).status_code == (200 if role == "read_only_auditor" else 403)
        assert (
            await other.post(API + f"/{row['id']}/file", files={"file": ("a.pdf", PDF)})
        ).status_code == 403
    async with rig["owner"].begin() as db:
        await db.execute(
            text("update memberships set role='employee' where company_id=:c and role='hr_admin'"),
            {"c": rig["a"]},
        )
    assert (await hr.get(f"/api/v1/files/{row['file_id']}/download")).status_code == 404


async def test_send_audit_failure_rolls_back_policy_assignments_and_messages(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    employee = await _employee(rig, rig["a"], "ATOMIC")
    await linked(rig, employee)
    async with rig["owner"].connect() as db:
        before_messages = (
            await db.execute(
                text("select count(*) from email_outbox where template='policy_request'")
            )
        ).scalar_one()
    row = await document(admin)

    async def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("policy audit failed")

    monkeypatch.setattr(service, "record", fail)
    response = await send(admin, row)
    assert response.status_code == 500
    assert (await admin.get(API + f"/{row['id']}")).json()["status"] == "draft"
    async with rig["owner"].connect() as db:
        assert (
            await db.execute(
                text("select count(*) from policy_acceptances where company_id=:c"), {"c": rig["a"]}
            )
        ).scalar_one() == 0
        assert (
            await db.execute(
                text("select count(*) from notifications where company_id=:c"), {"c": rig["a"]}
            )
        ).scalar_one() == 0
        assert (
            await db.execute(
                text("select count(*) from email_outbox where template='policy_request'")
            )
        ).scalar_one() == before_messages


async def test_remind_targets_outstanding_people_and_overdue_job_notifies_once(
    rig: dict[str, Any],
) -> None:
    origin = "https://app.example.test"
    admin = await rig["person"]("company_admin", rig["a"])
    first = await _employee(rig, rig["a"], "REM1")
    await _employee(rig, rig["a"], "REM2")
    member = await linked(rig, first)
    everyone = await document(admin, title="Remind everyone")
    assert (await admin.post(API + f"/{everyone['id']}/remind")).status_code == 409
    assert (await send(admin, everyone)).status_code == 200
    reminded = await admin.post(API + f"/{everyone['id']}/remind")
    assert reminded.status_code == 200, reminded.text
    assert reminded.json() == {"count": 2}
    accepted = await member.post(API + f"/{everyone['id']}/accept", json={"confirmed": True})
    assert accepted.status_code == 200, accepted.text
    assert (await admin.post(API + f"/{everyone['id']}/remind")).json() == {"count": 1}
    assert (await member.post(API + f"/{everyone['id']}/remind")).status_code == 403
    foreign = await rig["person"]("company_admin", rig["b"])
    assert (await foreign.post(API + f"/{everyone['id']}/remind")).status_code == 404
    named = await document(
        admin, title="Only the member", audience_type="named", audience_ids=[str(first)]
    )
    assert (await send(admin, named)).status_code == 200
    later = datetime.now(UTC) + timedelta(days=60)
    assert await reconcile_policies(rig["owner"], origin, now=later) >= 2
    assert await reconcile_policies(rig["owner"], origin, now=later) == 0
    statuses = {
        row["employee_id"]: row["status"]
        for row in (await admin.get(API + f"/{everyone['id']}/acceptances")).json()
    }
    assert statuses[str(first)] == "accepted"
    assert sorted(statuses.values()) == ["accepted", "overdue"]
    assert (await admin.post(API + f"/{everyone['id']}/remind")).json() == {"count": 1}
    inbox = (await member.get("/api/v1/notifications")).json()["items"]
    assert any(
        n["kind"] == "policy.overdue" and n["link"] == f"/my-documents?policy={named['id']}"
        for n in inbox
    )
    assert any(
        n["kind"] == "policy.reminder" and n["link"] == f"/my-documents?policy={everyone['id']}"
        for n in inbox
    )
    async with rig["owner"].connect() as db:
        overdue = (
            await db.execute(
                text(
                    "select count(*) from policy_acceptances where company_id=:c "
                    "and status='overdue'"
                ),
                {"c": rig["a"]},
            )
        ).scalar_one()
    assert overdue == 2


async def test_new_starters_join_marked_policies_on_hire_and_daily_catch_up(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    existing = await _employee(rig, rig["a"], "JOIN0")
    marked = await document(admin, title="Joiners pack", auto_send_new_starters=True)
    assert (await send(admin, marked)).status_code == 200
    plain = await document(admin, title="Optional reading")
    assert (await send(admin, plain)).status_code == 200
    hired = await admin.post(
        "/api/v1/employees",
        json={
            "first_name": "New",
            "last_name": "Starter",
            "email": "new.starter@example.com",
            "employee_number": "JOIN1",
            "hire_date": "2026-11-09",
        },
    )
    assert hired.status_code == 201, hired.text
    hired_id = hired.json()["id"]
    marked_people = {
        row["employee_id"] for row in (await admin.get(API + f"/{marked['id']}/acceptances")).json()
    }
    assert marked_people == {str(existing), hired_id}
    plain_people = {
        row["employee_id"] for row in (await admin.get(API + f"/{plain['id']}/acceptances")).json()
    }
    assert plain_people == {str(existing)}
    late = await _employee(rig, rig["a"], "JOIN2")
    assert await reconcile_policies(rig["owner"], "https://app.example.test") >= 1
    assert await reconcile_policies(rig["owner"], "https://app.example.test") == 0
    marked_after = {
        row["employee_id"]: row["status"]
        for row in (await admin.get(API + f"/{marked['id']}/acceptances")).json()
    }
    assert marked_after[str(late)] == "pending"
    assert len(marked_after) == 3
    plain_after = (await admin.get(API + f"/{plain['id']}/acceptances")).json()
    assert {row["employee_id"] for row in plain_after} == {str(existing)}
    async with rig["owner"].connect() as db:
        actions = set(
            (
                await db.execute(
                    text("select action from audit_events where company_id=:c"), {"c": rig["a"]}
                )
            ).scalars()
        )
    assert "policy.assigned_new_starters" in actions
