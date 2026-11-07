"""T14.1 dashboard: an employee sees no company-wide cards; cards show real counts; the checklist
reflects real data and stays dismissed; another company's figures never appear."""

from __future__ import annotations

import uuid
from typing import Any

from tests.db.test_employee_documents import rig as rig

API = "/api/v1"
COMPANY_WIDE = {
    "employees",
    "rtw",
    "off_today",
    "approvals",
    "distribution",
    "learning",
    "recruitment",
}


async def _staff(admin: Any, first: str) -> str:
    number = uuid.uuid4().hex[:10]
    made = await admin.post(
        API + "/employees",
        json={
            "first_name": first,
            "last_name": f"Card{number}",
            "employee_number": number,
            "email": f"{number}@example.com",
            "hire_date": "2025-01-01",
        },
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


async def test_an_employee_sees_no_company_wide_cards(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    await _staff(admin, "Ivy")
    employee = await rig["person"]("employee", rig["a"])
    body = (await employee.get(API + "/dashboard")).json()
    assert set(body) <= {"first_name", "status_line", "needs_attention", "my_learning"}
    assert not (set(body) & COMPANY_WIDE)
    assert body["needs_attention"] == []
    assert body["status_line"] == "Nothing needs your attention today"


async def test_an_administrator_sees_the_cards_with_real_counts(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    await _staff(admin, "Ada")
    await _staff(admin, "Ben")
    body = (await admin.get(API + "/dashboard")).json()
    assert {"employees", "rtw", "approvals", "distribution", "recruitment"} <= set(body)
    assert body["employees"] == {"active": 2, "on_leave": 0}
    assert body["rtw"]["checked"] == 2
    assert body["rtw"]["not_recorded"] == 2
    assert body["rtw"]["coverage_percent"] == 0
    # Both people have no department, so they sit in the Unassigned bucket.
    assert body["distribution"]["rows"] == [{"department": "Unassigned", "headcount": 2}]
    assert body["approvals"] == {"pending": 0}


async def test_the_setup_checklist_reflects_real_data_and_stays_dismissed(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    before = (await admin.get(API + "/onboarding/checklist")).json()
    assert before["visible"] is True
    assert before["total"] == 5
    labels = {item["key"]: item["done"] for item in before["items"]}
    assert labels["first_employee"] is False
    assert "sponsor_licence" not in labels  # no company sponsor-licence record exists yet

    await _staff(admin, "First")
    after = (await admin.get(API + "/onboarding/checklist")).json()
    assert {item["key"]: item["done"] for item in after["items"]}["first_employee"] is True
    assert after["done"] >= 1

    dismissed = await admin.post(API + "/onboarding/checklist/dismiss")
    assert dismissed.status_code == 204, dismissed.text
    assert (await admin.get(API + "/onboarding/checklist")).json()["visible"] is False
    assert (
        await admin.post(API + "/onboarding/checklist/dismiss")
    ).status_code == 204  # idempotent

    other = await rig["person"]("company_admin", rig["b"])
    assert (await other.get(API + "/onboarding/checklist")).json()["visible"] is True


async def test_another_company_never_sees_these_figures_and_employees_cannot_open_setup(
    rig: dict[str, Any],
) -> None:
    admin_a = await rig["person"]("company_admin", rig["a"])
    await _staff(admin_a, "Only")
    admin_b = await rig["person"]("company_admin", rig["b"])
    body = (await admin_b.get(API + "/dashboard")).json()
    assert body["employees"] == {"active": 0, "on_leave": 0}
    assert body["distribution"]["rows"] == []
    employee = await rig["person"]("employee", rig["a"])
    assert (await employee.get(API + "/onboarding/checklist")).status_code == 403
    assert (await employee.post(API + "/onboarding/checklist/dismiss")).status_code == 403
