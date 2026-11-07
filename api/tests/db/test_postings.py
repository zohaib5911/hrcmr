"""T11.2 postings: only open requisitions, unique slugs, and a public link only while external and open."""

from __future__ import annotations

import uuid
from typing import Any

from tests.db.test_employee_documents import rig as rig

API = "/api/v1"


async def open_requisition(admin: Any, title: str = "Warehouse operative") -> str:
    made = await admin.post(API + "/requisitions", json={"job_title": title, "headcount": 2})
    assert made.status_code == 201, made.text
    ident = made.json()["id"]
    opened = await admin.patch(f"{API}/requisitions/{ident}/status", json={"status": "open"})
    assert opened.status_code == 200, opened.text
    return str(ident)


def posting(requisition_id: str, **changes: Any) -> dict[str, Any]:
    return {
        "requisition_id": requisition_id,
        "title": "Warehouse operative",
        "visibility": "external",
        "vacancies": 2,
        "soc_code": "8111",
        "visa_sponsorship": "not_stated",
        **changes,
    }


async def test_a_posting_needs_an_open_requisition_and_slugs_are_unique(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    foreign = await rig["person"]("company_admin", rig["b"])
    draft = (await admin.post(API + "/requisitions", json={"job_title": "Cook"})).json()["id"]
    refused = await admin.post(API + "/postings", json=posting(draft))
    assert refused.status_code == 422, refused.text
    open_id = await open_requisition(admin)
    first = await admin.post(API + "/postings", json=posting(open_id))
    assert first.status_code == 201, first.text
    assert first.json()["slug"] == "warehouse-operative"
    second = await admin.post(API + "/postings", json=posting(open_id))
    assert second.status_code == 201, second.text
    assert second.json()["slug"] == "warehouse-operative-2"
    foreign_open = await open_requisition(foreign, title="Porter")
    leaked = await admin.post(API + "/postings", json=posting(foreign_open))
    assert leaked.status_code == 422, leaked.text


async def test_public_link_exists_only_while_external_and_open(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    req = await open_requisition(admin)
    made = await admin.post(API + "/postings", json=posting(req))
    assert made.status_code == 201, made.text
    row = made.json()
    base = f"{API}/postings/{row['id']}"
    assert row["status"] == "draft"
    assert row["public_link"] is None
    opened = await admin.patch(base + "/status", json={"status": "open"})
    assert opened.status_code == 200, opened.text
    link = opened.json()["public_link"]
    assert link is not None
    assert "/careers/" in link
    assert link.endswith("/warehouse-operative")
    closed = await admin.patch(base + "/status", json={"status": "closed"})
    assert closed.status_code == 200, closed.text
    assert closed.json()["public_link"] is None
    reopened = await admin.patch(base + "/status", json={"status": "open"})
    assert reopened.json()["public_link"] == link
    internal = await admin.patch(
        base, json=posting(req, visibility="internal", title="Warehouse operative")
    )
    assert internal.status_code == 200, internal.text
    assert internal.json()["public_link"] is None


async def test_status_rules_and_an_approved_requisition_is_needed_to_reopen(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    req = await open_requisition(admin)
    row = (await admin.post(API + "/postings", json=posting(req))).json()
    base = f"{API}/postings/{row['id']}"
    assert (await admin.patch(base + "/status", json={"status": "open"})).status_code == 200
    assert (await admin.patch(base + "/status", json={"status": "draft"})).status_code == 409
    assert (await admin.patch(base + "/status", json={"status": "closed"})).status_code == 200
    cancelled = await admin.patch(f"{API}/requisitions/{req}/status", json={"status": "cancelled"})
    assert cancelled.status_code == 200, cancelled.text
    reopen = await admin.patch(base + "/status", json={"status": "open"})
    assert reopen.status_code == 422, reopen.text


async def test_validation_roles_and_locations(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    recruiter = await rig["person"]("recruiter", rig["a"])
    employee = await rig["person"]("employee", rig["a"])
    req = await open_requisition(admin)
    assert (
        await admin.post(
            API + "/postings",
            json=posting(req, posted_on="2026-11-10", closes_on="2026-11-01"),
        )
    ).status_code == 422
    assert (
        await admin.post(API + "/postings", json=posting(req, soc_code="21a"))
    ).status_code == 422
    assert (
        await admin.post(API + "/postings", json=posting(req, location_id=str(uuid.uuid4())))
    ).status_code == 422
    made = await recruiter.post(API + "/postings", json=posting(req))
    assert made.status_code == 201, made.text
    assert (await employee.post(API + "/postings", json=posting(req))).status_code == 403
    assert (await employee.get(API + "/postings")).status_code == 403
