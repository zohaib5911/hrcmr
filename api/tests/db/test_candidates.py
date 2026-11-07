"""T11.3 candidates: CRUD, archive, and a right-to-work check that records and shows its status."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from tests.db.test_employee_documents import rig as rig

API = "/api/v1"


async def test_candidates_are_added_edited_and_archived(rig: dict[str, Any]) -> None:
    recruiter = await rig["person"]("recruiter", rig["a"])
    made = await recruiter.post(
        API + "/candidates",
        json={
            "first_name": "Lena",
            "last_name": "Ortiz",
            "email": "lena@example.com",
            "source": "Referral",
        },
    )
    assert made.status_code == 201, made.text
    row = made.json()
    assert row["rtw_status"] == "not_recorded"
    assert row["archived"] is False
    edited = await recruiter.patch(
        f"{API}/candidates/{row['id']}",
        json={"first_name": "Lena", "last_name": "Ortiz-Diaz", "email": "lena@example.com"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["last_name"] == "Ortiz-Diaz"
    listed = (await recruiter.get(API + "/candidates", params={"search": "ortiz"})).json()
    assert [item["id"] for item in listed["items"]] == [row["id"]]
    assert (await recruiter.delete(f"{API}/candidates/{row['id']}")).status_code == 204
    assert (await recruiter.get(API + "/candidates")).json()["total"] == 0
    shown = (await recruiter.get(API + "/candidates", params={"include_archived": "true"})).json()
    assert shown["items"][0]["archived"] is True


async def test_a_right_to_work_check_records_and_shows_its_status(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    row = (
        await admin.post(API + "/candidates", json={"first_name": "Omar", "last_name": "Reid"})
    ).json()
    me = (await admin.get(API + "/auth/me")).json()["user"]["id"]
    check = {
        "check_type": "manual_list_a",
        "check_date": (datetime.now(UTC).date() - timedelta(days=1)).isoformat(),
        "checked_by_user_id": me,
        "outcome": "verified",
    }
    recorded = await admin.post(f"{API}/candidates/{row['id']}/rtw-checks", json=check)
    assert recorded.status_code == 201, recorded.text
    assert recorded.json()["status"] == "evidence_missing"
    again = await admin.post(
        f"{API}/candidates/{row['id']}/rtw-checks", json={**check, "outcome": "failed"}
    )
    assert again.status_code == 201, again.text
    tab = (await admin.get(f"{API}/candidates/{row['id']}/rtw-checks")).json()
    assert tab["status"] == "failed"
    assert tab["current"]["outcome"] == "failed"
    assert len(tab["checks"]) == 2
    listed = (await admin.get(API + "/candidates")).json()
    assert listed["items"][0]["rtw_status"] == "failed"


async def test_other_companies_are_404_and_employees_are_refused(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    foreign = await rig["person"]("company_admin", rig["b"])
    employee = await rig["person"]("employee", rig["a"])
    row = (
        await admin.post(API + "/candidates", json={"first_name": "Priya", "last_name": "Nair"})
    ).json()
    base = f"{API}/candidates/{row['id']}"
    assert (await foreign.get(base)).status_code == 404
    assert (
        await foreign.patch(base, json={"first_name": "X", "last_name": "Y"})
    ).status_code == 404
    assert (await foreign.get(base + "/rtw-checks")).status_code == 404
    assert (await foreign.delete(base)).status_code == 404
    assert (await employee.get(API + "/candidates")).status_code == 403
    assert (await employee.get(base + "/rtw-checks")).status_code == 403
