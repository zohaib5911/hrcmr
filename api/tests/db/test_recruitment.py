"""T11.1 requisitions: only an approver opens one, approvals are stamped, tenants stay apart."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text

from tests.db.test_employee_documents import rig as rig

API = "/api/v1"


def requisition(**changes: Any) -> dict[str, Any]:
    return {"job_title": "Warehouse operative", "headcount": 2, **changes}


async def test_only_an_approver_can_open_and_the_approval_is_stamped(rig: dict[str, Any]) -> None:
    recruiter = await rig["person"]("recruiter", rig["a"])
    admin = await rig["person"]("company_admin", rig["a"])
    made = await recruiter.post(
        API + "/requisitions",
        json=requisition(budget_from="20000.00", budget_to="24000.00", budget_per="year"),
    )
    assert made.status_code == 201, made.text
    row = made.json()
    assert row["status"] == "draft"
    assert row["approved_at"] is None
    assert row["approved_by_name"] is None
    url = f"{API}/requisitions/{row['id']}/status"
    assert (await recruiter.patch(url, json={"status": "open"})).status_code == 403
    assert (await recruiter.get(f"{API}/requisitions/{row['id']}")).json()["status"] == "draft"
    held = await recruiter.patch(url, json={"status": "on_hold"})
    assert held.status_code == 200, held.text
    assert held.json()["status"] == "on_hold"
    opened = await admin.patch(url, json={"status": "open"})
    assert opened.status_code == 200, opened.text
    body = opened.json()
    assert body["status"] == "open"
    assert body["approved_at"] is not None
    assert "approved_by_name" in body
    reply = await admin.get(f"{API}/recruitment/summary")
    assert reply.status_code == 200, reply.text
    summary = reply.json()
    assert summary["open_requisitions"] == 1
    assert summary["requisitions"] == 1
    async with rig["owner"].connect() as db:
        actions = set(
            (
                await db.execute(
                    text("select action from audit_events where company_id=:c"), {"c": rig["a"]}
                )
            ).scalars()
        )
    assert {"recruitment.requisition.created", "recruitment.requisition.status_changed"} <= actions


async def test_other_companies_cannot_reach_and_a_cancelled_requisition_is_final(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    foreign = await rig["person"]("company_admin", rig["b"])
    row = (await admin.post(API + "/requisitions", json=requisition())).json()
    base = f"{API}/requisitions/{row['id']}"
    assert (await foreign.get(base)).status_code == 404
    assert (await foreign.patch(base, json=requisition(job_title="Taken"))).status_code == 404
    assert (await foreign.patch(base + "/status", json={"status": "cancelled"})).status_code == 404
    cancelled = await admin.patch(base + "/status", json={"status": "cancelled"})
    assert cancelled.status_code == 200, cancelled.text
    assert (await admin.patch(base + "/status", json={"status": "open"})).status_code == 409
    assert (await admin.patch(base, json=requisition(job_title="Changed"))).status_code == 409


async def test_bad_input_and_employees_are_refused(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    employee = await rig["person"]("employee", rig["a"])
    assert (
        await admin.post(
            API + "/requisitions", json=requisition(budget_from="30000", budget_to="20000")
        )
    ).status_code == 422
    assert (
        await admin.post(API + "/requisitions", json=requisition(department_id=str(uuid.uuid4())))
    ).status_code == 422
    row = (await admin.post(API + "/requisitions", json=requisition())).json()
    assert (
        await admin.patch(f"{API}/requisitions/{row['id']}/status", json={"status": "approved"})
    ).status_code == 422
    assert (await employee.get(API + "/requisitions")).status_code == 403
    assert (await employee.post(API + "/requisitions", json=requisition())).status_code == 403
    assert (await employee.get(API + "/recruitment/summary")).status_code == 403
