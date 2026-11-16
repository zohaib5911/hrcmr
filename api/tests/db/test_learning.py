"""T13.1 learning: courses are our content (edited only by super-admin), learners see only their own
assignments and no answers, progress survives a reload, and a check below the pass mark never
completes a course."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.learning.loader import load_courses
from tests.db.test_employee_documents import rig as rig
from tests.support import step_up

API = "/api/v1"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "courses"
SLUG = "e2e-test-course"


def _course_body(slug: str, *, published: bool = False) -> dict[str, Any]:
    return {
        "slug": slug,
        "title": "Editor test course",
        "summary": "A course written for the editor tests.",
        "duration_minutes": 15,
        "audience": "all_staff",
        "sections": [
            {"title": f"Part {i}", "body": "Some text.", "key_points": []} for i in (1, 2, 3)
        ],
        "quiz": {
            "questions": [
                {
                    "prompt": "First?",
                    "options": ["a", "b", "c"],
                    "answer": 0,
                    "explanation": "Because a.",
                },
                {
                    "prompt": "Second?",
                    "options": ["a", "b"],
                    "answer": 1,
                    "explanation": "Because b.",
                },
            ]
        },
        "pass_mark": 60,
        "source_title": "A GOV.UK page",
        "source_publisher": "GOV.UK",
        "source_url": "https://www.gov.uk/guidance/example",
        "source_updated_on": "2026-11-03",
        "content_reviewed_on": "2026-11-07",
        "licence_note": None,
        "published": published,
    }


async def _as_platform_admin(rig: dict[str, Any], admin: Any) -> None:
    """Gives the signed-in administrator platform access with MFA, as the dossier tests do."""
    platform_id = next(
        u["user_id"] for u in (await admin.get(API + "/users")).json()["users"] if u["is_you"]
    )
    async with rig["owner"].begin() as c:
        await c.execute(
            text("insert into platform_admins (user_id,level) values (:u,'support')"),
            {"u": platform_id},
        )
        await c.execute(text("update users set mfa_enabled=true where id=:u"), {"u": platform_id})
    # The platform cookie (T17.1): the admin pages accept nothing else.
    await step_up(admin)
    started = await admin.post(API + "/auth/platform-session")
    assert started.status_code == 201, started.text


async def _load_fixture(rig: dict[str, Any]) -> str:
    async with AsyncSession(rig["owner"]) as db:
        await load_courses(db, FIXTURES)
        await db.commit()
    courses = (
        await (await rig["person"]("company_admin", rig["a"])).get(API + "/learning/courses")
    ).json()
    return str(next(course["id"] for course in courses if course["slug"] == SLUG))


async def _link_me(admin: Any) -> str:
    """A new employee, linked to the signed-in administrator (who can then have own assignments)."""
    person = await admin.post(
        API + "/employees",
        json={
            "first_name": "Mina",
            "last_name": uuid.uuid4().hex[:6],
            "employee_number": uuid.uuid4().hex[:10],
            "email": f"{uuid.uuid4().hex[:10]}@example.com",
            "hire_date": "2025-01-01",
        },
    )
    assert person.status_code == 201, person.text
    employee = person.json()["id"]
    me = next(u for u in (await admin.get(API + "/users")).json()["users"] if u["is_you"])
    linked = await admin.put(f"{API}/users/{me['id']}/employee", json={"employee_id": employee})
    assert linked.status_code == 200, linked.text
    return str(employee)


async def test_the_editor_is_for_platform_admins_and_checks_the_content(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    slug = f"course-{uuid.uuid4().hex[:8]}"
    assert (await admin.get(API + "/admin/courses")).status_code == 403
    assert (await admin.post(API + "/admin/courses", json=_course_body(slug))).status_code == 403
    await _as_platform_admin(rig, admin)

    created = await admin.post(API + "/admin/courses", json=_course_body(slug))
    assert created.status_code == 201, created.text
    course = created.json()
    assert course["version"] == 1
    assert course["published"] is False
    assert course["questions"][0]["answer"] == 0  # the editor sees the answers

    again = await admin.post(API + "/admin/courses", json=_course_body(slug))
    assert again.status_code == 409, again.text

    bad_answer = _course_body(f"{slug}-x")
    bad_answer["quiz"]["questions"][0]["answer"] = 3  # not one of three options
    assert (await admin.post(API + "/admin/courses", json=bad_answer)).status_code == 422

    too_few_sections = _course_body(f"{slug}-y")
    too_few_sections["sections"] = too_few_sections["sections"][:2]
    assert (await admin.post(API + "/admin/courses", json=too_few_sections)).status_code == 422

    http_source = _course_body(f"{slug}-z")
    http_source["source_url"] = "http://www.gov.uk/guidance/example"
    assert (await admin.post(API + "/admin/courses", json=http_source)).status_code == 422

    changed = _course_body(slug, published=True)
    changed["title"] = "Editor test course, revised"
    updated = await admin.put(f"{API}/admin/courses/{course['id']}", json=changed)
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2
    assert updated.json()["published"] is True

    same = await admin.put(f"{API}/admin/courses/{course['id']}", json=changed)
    assert same.json()["version"] == 2  # no change in content, no new version


async def test_learners_see_published_courses_without_answers_and_only_their_own(
    rig: dict[str, Any],
) -> None:
    course_id = await _load_fixture(rig)
    admin = await rig["person"]("company_admin", rig["a"])
    me = await _link_me(admin)
    other = await admin.post(
        API + "/employees",
        json={
            "first_name": "Other",
            "last_name": uuid.uuid4().hex[:6],
            "employee_number": uuid.uuid4().hex[:10],
            "email": f"{uuid.uuid4().hex[:10]}@example.com",
            "hire_date": "2025-01-01",
        },
    )
    other_id = other.json()["id"]

    course = await admin.get(f"{API}/learning/courses/{course_id}")
    assert course.status_code == 200, course.text
    assert '"answer"' not in course.text
    assert '"explanation"' not in course.text
    assert len(course.json()["questions"]) == 2
    assert len(course.json()["sections"]) == 3

    assigned = await admin.post(
        API + "/learning/assignments",
        json={"course_ids": [course_id], "employee_ids": [me, other_id], "due_on": "2026-12-01"},
    )
    assert assigned.status_code == 201, assigned.text
    assert assigned.json() == {"created": 2, "already_assigned": 0}
    again = await admin.post(
        API + "/learning/assignments",
        json={"course_ids": [course_id], "employee_ids": [me], "due_on": "2026-12-01"},
    )
    assert again.json() == {"created": 0, "already_assigned": 1}  # assigning twice adds nothing

    mine = (await admin.get(API + "/learning/assignments/own")).json()
    assert [row["slug"] for row in mine] == [SLUG]
    assert mine[0]["status"] == "not_started"
    assert mine[0]["passed"] is False
    # Someone else's assignment is not found, the same as a missing one. Company B cannot see
    # company A's assignment, and has no assignments of its own.
    stranger = await rig["person"]("company_admin", rig["b"])
    assert (await stranger.get(f"{API}/learning/assignments/{mine[0]['id']}")).status_code == 404
    assert (await stranger.get(f"{API}/learning/assignments/own")).json() == []

    employee = await rig["person"]("employee", rig["a"])
    assert (
        await employee.post(
            API + "/learning/assignments",
            json={"course_ids": [course_id], "employee_ids": [me], "due_on": "2026-12-01"},
        )
    ).status_code == 403


async def test_progress_survives_a_reload_and_a_check_below_the_pass_mark_does_not_complete(
    rig: dict[str, Any],
) -> None:
    course_id = await _load_fixture(rig)
    admin = await rig["person"]("company_admin", rig["a"])
    me = await _link_me(admin)
    await admin.post(
        API + "/learning/assignments",
        json={"course_ids": [course_id], "employee_ids": [me], "due_on": "2026-12-01"},
    )
    assignment = (await admin.get(API + "/learning/assignments/own")).json()[0]["id"]
    base = f"{API}/learning/assignments/{assignment}"

    saved = await admin.post(base + "/progress", json={"section": 2})
    assert saved.status_code == 200, saved.text
    assert saved.json()["section"] == 2
    assert saved.json()["status"] == "in_progress"
    reloaded = (await admin.get(base)).json()
    assert reloaded["assignment"]["section"] == 2  # the player resumes where the learner left off
    assert (await admin.post(base + "/progress", json={"section": 3})).status_code == 422

    assert (await admin.post(base + "/complete")).status_code == 409  # no check yet

    wrong = await admin.post(base + "/quiz", json={"answers": [0, 0]})
    assert wrong.status_code == 200, wrong.text
    assert wrong.json()["score"] == 0
    assert wrong.json()["passed"] is False
    assert [r["correct_option"] for r in wrong.json()["results"]] == [2, 1]
    assert (await admin.post(base + "/complete")).status_code == 409

    half = await admin.post(base + "/quiz", json={"answers": [2, 0]})
    assert half.json()["score"] == 50
    assert half.json()["passed"] is False
    assert (await admin.post(base + "/complete")).status_code == 409
    assert (await admin.get(base)).json()["assignment"]["status"] == "in_progress"

    assert (await admin.post(base + "/quiz", json={"answers": [2]})).status_code == 422

    right = await admin.post(base + "/quiz", json={"answers": [2, 1]})
    assert right.json()["score"] == 100
    assert right.json()["passed"] is True
    done = await admin.post(base + "/complete")
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "completed"
    assert done.json()["completed_at"] is not None

    # A later, worse attempt keeps the best score and the completion.
    later = await admin.post(base + "/quiz", json={"answers": [0, 0]})
    assert later.json()["best_score"] == 100
    assert (await admin.get(base)).json()["assignment"]["status"] == "completed"


async def test_unpublished_courses_stay_hidden_from_learners(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    await _as_platform_admin(rig, admin)
    slug = f"draft-{uuid.uuid4().hex[:6]}"
    draft = await admin.post(API + "/admin/courses", json=_course_body(slug, published=False))
    assert draft.status_code == 201, draft.text
    assert all(
        course["slug"] != slug for course in (await admin.get(API + "/learning/courses")).json()
    )
    assert (await admin.get(f"{API}/learning/courses/{draft.json()['id']}")).status_code == 404
