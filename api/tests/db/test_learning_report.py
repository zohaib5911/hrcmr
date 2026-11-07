"""T13.3 learning: assigning to everyone, a department or named people never duplicates; the report
filters; the export opens; the overdue job flips and notifies once; an employee sees only their own."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.learning import reconcile_learning
from app.modules.learning.loader import load_courses
from tests.db.test_employee_documents import rig as rig

API = "/api/v1"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "courses"
SLUG = "e2e-test-course"


async def _course(rig: dict[str, Any]) -> str:
    async with AsyncSession(rig["owner"]) as db:
        await load_courses(db, FIXTURES)
        await db.commit()
    courses = (
        await (await rig["person"]("company_admin", rig["a"])).get(API + "/learning/courses")
    ).json()
    return str(next(course["id"] for course in courses if course["slug"] == SLUG))


async def _department(admin: Any, name: str) -> str:
    made = await admin.post(API + "/departments", json={"name": name})
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


async def _staff(admin: Any, first: str, department: str | None) -> str:
    number = uuid.uuid4().hex[:10]
    made = await admin.post(
        API + "/employees",
        json={
            "first_name": first,
            "last_name": f"Staff{number}",
            "employee_number": number,
            "email": f"{number}@example.com",
            "hire_date": "2025-01-01",
        },
    )
    assert made.status_code == 201, made.text
    person = str(made.json()["id"])
    if department is not None:
        role = await admin.post(
            f"{API}/employees/{person}/assignments",
            json={
                "employment_type": "full_time",
                "effective_from": "2025-01-01",
                "department_id": department,
            },
        )
        assert role.status_code == 201, role.text
    return person


async def test_scopes_never_duplicate_and_the_report_filters_and_exports(
    rig: dict[str, Any],
) -> None:
    course = await _course(rig)
    admin = await rig["person"]("company_admin", rig["a"])
    kitchen_name = f"Kitchen {uuid.uuid4().hex[:6]}"
    kitchen = await _department(admin, kitchen_name)
    front = await _department(admin, f"Front {uuid.uuid4().hex[:6]}")
    chef = await _staff(admin, "Chef", kitchen)
    cook = await _staff(admin, "Cook", kitchen)
    host = await _staff(admin, "Host", front)
    base = API + "/learning/assignments"

    by_department = await admin.post(
        base,
        json={
            "course_ids": [course],
            "scope": "departments",
            "department_ids": [kitchen],
            "due_on": "2026-12-01",
        },
    )
    assert by_department.status_code == 201, by_department.text
    assert by_department.json() == {"created": 2, "already_assigned": 0}
    again = await admin.post(
        base,
        json={
            "course_ids": [course],
            "scope": "departments",
            "department_ids": [kitchen],
            "due_on": "2026-12-01",
        },
    )
    assert again.json() == {"created": 0, "already_assigned": 2}  # assigning twice adds nothing

    everyone = await admin.post(
        base, json={"course_ids": [course], "scope": "everyone", "due_on": "2026-12-01"}
    )
    assert everyone.status_code == 201, everyone.text
    total_people = everyone.json()["created"] + everyone.json()["already_assigned"]
    assert total_people == 3
    assert everyone.json()["already_assigned"] == 2  # the two kitchen staff were already assigned

    named = await admin.post(
        base,
        json={
            "course_ids": [course],
            "scope": "named",
            "employee_ids": [host],
            "due_on": "2026-12-01",
        },
    )
    assert named.json() == {"created": 0, "already_assigned": 1}

    refused = await admin.post(
        base,
        json={
            "course_ids": [course],
            "scope": "departments",
            "department_ids": [],
            "due_on": "2026-12-01",
        },
    )
    assert refused.status_code == 422, refused.text

    everyone_rows = (await admin.get(base)).json()
    assert everyone_rows["total"] == 3
    kitchen_rows = (await admin.get(base, params={"department_id": kitchen})).json()
    assert kitchen_rows["total"] == 2
    assert {row["employee_id"] for row in kitchen_rows["items"]} == {chef, cook}
    assert {row["department"] for row in kitchen_rows["items"]} == {kitchen_name}
    searched = (await admin.get(base, params={"search": "chef"})).json()
    assert searched["total"] == 1
    assert searched["items"][0]["employee_name"].startswith("Chef Staff")
    not_started = (await admin.get(base, params={"status": "not_started"})).json()
    assert not_started["total"] == 3

    summary = (await admin.get(API + "/learning/summary")).json()
    assert summary["assignments"] == 3
    assert summary["not_started"] == 3
    assert summary["overdue"] == 0

    export = await admin.get(base + ".xlsx")
    assert export.status_code == 200, export.text
    assert export.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert export.content.startswith(b"PK")  # an .xlsx file is a zip archive
    assert "no-store" in export.headers["cache-control"]


async def test_an_employee_sees_only_their_own_assignments_and_no_report(
    rig: dict[str, Any],
) -> None:
    await _course(rig)
    admin = await rig["person"]("company_admin", rig["a"])
    employee = await rig["person"]("employee", rig["a"])
    await _staff(admin, "Other", None)
    base = API + "/learning/assignments"
    assert (await employee.get(base)).status_code == 403
    assert (await employee.get(API + "/learning/summary")).status_code == 403
    assert (await employee.get(base + ".xlsx")).status_code == 403
    assert (await employee.get(API + "/learning/assignments/own")).json() == []


async def test_the_overdue_job_flips_once_and_tells_the_person(rig: dict[str, Any]) -> None:
    course = await _course(rig)
    admin = await rig["person"]("company_admin", rig["a"])
    member = next(u for u in (await admin.get(API + "/users")).json()["users"] if u["is_you"])
    mine = await _staff(admin, "Late", None)
    assert (
        await admin.put(f"{API}/users/{member['id']}/employee", json={"employee_id": mine})
    ).status_code == 200
    assigned = await admin.post(
        API + "/learning/assignments",
        json={
            "course_ids": [course],
            "scope": "named",
            "employee_ids": [mine],
            "due_on": "2026-11-01",
        },
    )
    assert assigned.status_code == 201, assigned.text
    before = (await admin.get(API + "/learning/summary")).json()
    assert before["overdue"] == 1  # computed today, before the job has run

    now = datetime(2026, 11, 7, 6, 15, tzinfo=UTC)
    assert await reconcile_learning(rig["owner"], now=now) >= 1
    async with rig["owner"].connect() as c:
        status = (
            await c.execute(
                text("select status from course_assignments where employee_id = :e"), {"e": mine}
            )
        ).scalar_one()
        first = (
            await c.execute(
                text(
                    "select count(*) from notifications where kind = 'learning.overdue' and user_id = :u"
                ),
                {"u": member["user_id"]},
            )
        ).scalar_one()
    assert status == "overdue"
    assert first == 1

    assert await reconcile_learning(rig["owner"], now=now) == 0  # a second run changes nothing
    async with rig["owner"].connect() as c:
        second = (
            await c.execute(
                text(
                    "select count(*) from notifications where kind = 'learning.overdue' and user_id = :u"
                ),
                {"u": member["user_id"]},
            )
        ).scalar_one()
    assert second == 1  # and nobody is told twice
    own = (await admin.get(API + "/learning/assignments/own")).json()
    assert own[0]["status"] == "overdue"
