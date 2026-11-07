"""T11.4 offers: draft, then sent, then accepted or declined; decided offers are final."""

from __future__ import annotations

from typing import Any

from tests.db.test_applications import candidate, open_posting
from tests.db.test_employee_documents import rig as rig

API = "/api/v1"


async def application(admin: Any, first: str, title: str) -> str:
    posting = await open_posting(admin, title)
    who = await candidate(admin, first)
    made = await admin.post(
        API + "/applications", json={"candidate_id": who, "posting_id": posting}
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


async def test_an_offer_moves_from_draft_to_sent_to_accepted(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    app = await application(admin, "Ines", "Line cook")
    made = await admin.post(
        f"{API}/applications/{app}/offers",
        json={
            "role_title": "Line cook",
            "salary": "26000.00",
            "salary_per": "year",
            "start_date": "2026-12-01",
        },
    )
    assert made.status_code == 201, made.text
    offer = made.json()
    assert offer["status"] == "draft"
    assert offer["salary"] == "26000.00"
    url = f"{API}/offers/{offer['id']}"
    early = await admin.patch(url, json={"status": "accepted"})
    assert early.status_code == 409, early.text
    sent = await admin.patch(url, json={"status": "sent"})
    assert sent.status_code == 200, sent.text
    locked = await admin.patch(url, json={"salary": "27000.00"})
    assert locked.status_code == 409
    accepted = await admin.patch(url, json={"status": "accepted"})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["decided_at"] is not None
    final = await admin.patch(url, json={"status": "declined"})
    assert final.status_code == 409
    listed = (await admin.get(f"{API}/applications/{app}/offers")).json()
    assert [row["status"] for row in listed] == ["accepted"]


async def test_ended_applications_take_no_offers_and_other_companies_get_404(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    foreign = await rig["person"]("company_admin", rig["b"])
    app = await application(admin, "Jo", "Porter")
    offer = (
        await admin.post(
            f"{API}/applications/{app}/offers",
            json={"role_title": "Porter", "salary": "21000", "salary_per": "year"},
        )
    ).json()
    assert (
        await admin.post(f"{API}/applications/{app}/stage", json={"stage": "rejected"})
    ).status_code == 200
    refused = await admin.post(
        f"{API}/applications/{app}/offers",
        json={"role_title": "Porter", "salary": "21000", "salary_per": "year"},
    )
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "APPLICATION_ENDED"
    assert (
        await foreign.patch(f"{API}/offers/{offer['id']}", json={"status": "sent"})
    ).status_code == 404


async def test_employees_cannot_see_offers(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    employee = await rig["person"]("employee", rig["a"])
    app = await application(admin, "Kit", "Dishwasher")
    assert (await employee.get(f"{API}/applications/{app}/offers")).status_code == 403
