"""T11.4 applications: one stage at a time, a fixed message on a skip, and counts that match the database."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from tests.db.test_employee_documents import rig as rig

API = "/api/v1"


async def open_posting(admin: Any, title: str) -> str:
    req = (await admin.post(API + "/requisitions", json={"job_title": title})).json()["id"]
    assert (
        await admin.patch(f"{API}/requisitions/{req}/status", json={"status": "open"})
    ).status_code == 200
    made = await admin.post(
        API + "/postings",
        json={"requisition_id": req, "title": title, "visibility": "external", "vacancies": 1},
    )
    assert made.status_code == 201, made.text
    posting = made.json()["id"]
    opened = await admin.patch(f"{API}/postings/{posting}/status", json={"status": "open"})
    assert opened.status_code == 200, opened.text
    return str(posting)


async def candidate(admin: Any, first: str) -> str:
    made = await admin.post(API + "/candidates", json={"first_name": first, "last_name": "Test"})
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


async def test_applications_move_one_step_at_a_time_and_keep_history(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    posting = await open_posting(admin, "Barista")
    who = await candidate(admin, "Ada")
    made = await admin.post(
        API + "/applications", json={"candidate_id": who, "posting_id": posting}
    )
    assert made.status_code == 201, made.text
    app = made.json()
    assert app["stage"] == "applied"
    assert app["stage_label"] == "Job Applied"
    assert len(app["stage_history"]) == 1
    again = await admin.post(
        API + "/applications", json={"candidate_id": who, "posting_id": posting}
    )
    assert again.status_code == 409
    move = f"{API}/applications/{app['id']}/stage"
    skipped = await admin.post(move, json={"stage": "interview"})
    assert skipped.status_code == 422, skipped.text
    assert skipped.json()["error"]["message"] == "The next step from Job Applied is Shortlisted"
    assert (await admin.post(move, json={"stage": "shortlisted"})).status_code == 200
    back = await admin.post(move, json={"stage": "applied"})
    assert back.status_code == 200, back.text
    history = back.json()["stage_history"]
    assert [entry["stage"] for entry in history] == ["applied", "shortlisted", "applied"]
    assert all(entry["at"] for entry in history)
    ended = await admin.post(move, json={"stage": "rejected"})
    assert ended.status_code == 200, ended.text
    locked = await admin.post(move, json={"stage": "shortlisted"})
    assert locked.status_code == 422
    assert locked.json()["error"]["message"] == "This application is rejected. It cannot change."


async def test_closed_postings_take_no_applications_and_other_companies_get_404(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    foreign = await rig["person"]("company_admin", rig["b"])
    posting = await open_posting(admin, "Porter")
    who = await candidate(admin, "Bea")
    made = await admin.post(
        API + "/applications", json={"candidate_id": who, "posting_id": posting}
    )
    app = made.json()
    assert (
        await admin.patch(f"{API}/postings/{posting}/status", json={"status": "closed"})
    ).status_code == 200
    other = await candidate(admin, "Cy")
    refused = await admin.post(
        API + "/applications", json={"candidate_id": other, "posting_id": posting}
    )
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "POSTING_NOT_OPEN"
    assert (await foreign.get(f"{API}/applications/{app['id']}")).status_code == 404
    assert (
        await foreign.post(f"{API}/applications/{app['id']}/stage", json={"stage": "rejected"})
    ).status_code == 404


async def test_the_pipeline_counts_match_the_database(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    posting = await open_posting(admin, "Chef")
    for name in ("Dev", "Eli", "Fay"):
        who = await candidate(admin, name)
        made = await admin.post(
            API + "/applications", json={"candidate_id": who, "posting_id": posting}
        )
        assert made.status_code == 201, made.text
    first = (await admin.get(API + "/applications")).json()["items"][0]
    assert (
        await admin.post(f"{API}/applications/{first['id']}/stage", json={"stage": "shortlisted"})
    ).status_code == 200
    shown = (await admin.get(API + "/recruitment/pipeline")).json()
    counts = {item["stage"]: item["count"] for item in shown["stages"]}
    async with rig["owner"].connect() as db:
        rows = (
            await db.execute(
                text("select stage, count(*) from applications where company_id=:c group by stage"),
                {"c": rig["a"]},
            )
        ).all()
    database = {stage: int(total) for stage, total in rows}
    assert counts["applied"] == database.get("applied", 0) == 2
    assert counts["shortlisted"] == database.get("shortlisted", 0) == 1
    assert shown["total"] == sum(database.values()) == 3
    assert len(shown["stages"]) == 8


async def test_employees_are_refused(rig: dict[str, Any]) -> None:
    employee = await rig["person"]("employee", rig["a"])
    assert (await employee.get(API + "/applications")).status_code == 403
    assert (await employee.get(API + "/recruitment/pipeline")).status_code == 403
