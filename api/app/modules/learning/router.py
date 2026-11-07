"""Learning for employees: the course library, assignments, the player and the check (plan 8.14).

Only the person a course is assigned to can see it, record progress, sit the check or complete it.
A check that is below the pass mark never completes a course.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.errors import AppError, ConflictError, NotFoundError
from app.db.ids import uuid7
from app.modules.employees.models import Employee
from app.modules.learning import service
from app.modules.learning.models import Course, CourseAssignment
from app.modules.learning.schemas import (
    AssignmentCreatedOut,
    AssignmentDetailOut,
    CourseAssignmentIn,
    CourseAssignmentOut,
    CourseCardOut,
    CourseOut,
    ProgressIn,
    QuizAnswersIn,
    QuizResultOut,
)
from app.modules.rbac.deps import Access, require

router = APIRouter(tags=["learning"])
CourseReads = Annotated[Access, Depends(require("learning.course.read"))]
AssignWrites = Annotated[Access, Depends(require("learning.assignment.write"))]
OwnReads = Annotated[Access, Depends(require("learning.assignment.read_own"))]
OwnWrites = Annotated[Access, Depends(require("learning.assignment.complete_own"))]

CURRENT_STATUSES = ("active", "on_leave")  # people who can be assigned a course


async def _own(
    access: Access, assignment_id: uuid.UUID, *, lock: bool = False
) -> tuple[CourseAssignment, Course]:
    """The assignment and its course, only when it is the caller's own and the course is published.

    Anyone else, and any unknown id, gets the same "not found" answer.
    """
    if access.employee_id is None:
        raise NotFoundError
    query = (
        select(CourseAssignment, Course)
        .join(Course, Course.id == CourseAssignment.course_id)
        .where(
            CourseAssignment.id == assignment_id,
            CourseAssignment.company_id == access.company_id,
            CourseAssignment.employee_id == access.employee_id,
            Course.published.is_(True),
        )
    )
    if lock:
        query = query.with_for_update(of=CourseAssignment)
    found = (await access.db.execute(query)).first()
    if found is None:
        raise NotFoundError
    row, course = found
    return row, course


@router.get("/learning/courses", response_model=list[CourseCardOut])
async def list_courses(access: CourseReads) -> list[CourseCardOut]:
    rows = (
        (
            await access.db.execute(
                select(Course).where(Course.published.is_(True)).order_by(Course.title)
            )
        )
        .scalars()
        .all()
    )
    return [service.card_out(row) for row in rows]


@router.get("/learning/courses/{course_id}", response_model=CourseOut)
async def get_course(course_id: uuid.UUID, access: CourseReads) -> CourseOut:
    return service.learner_out(await service.course_or_404(access.db, course_id))


@router.post("/learning/assignments", status_code=201, response_model=AssignmentCreatedOut)
async def assign_courses(body: CourseAssignmentIn, access: AssignWrites) -> AssignmentCreatedOut:
    course_ids = set(body.course_ids)
    employee_ids = set(body.employee_ids)
    published = (
        (
            await access.db.execute(
                select(Course.id).where(Course.id.in_(course_ids), Course.published.is_(True))
            )
        )
        .scalars()
        .all()
    )
    if len(set(published)) != len(course_ids):
        raise AppError(
            "VALIDATION_ERROR",
            "Choose published courses.",
            status_code=422,
            field="course_ids",
        )
    people = (
        (
            await access.db.execute(
                select(Employee.id).where(
                    Employee.id.in_(employee_ids),
                    Employee.company_id == access.company_id,
                    Employee.status.in_(CURRENT_STATUSES),
                )
            )
        )
        .scalars()
        .all()
    )
    if len(set(people)) != len(employee_ids):
        raise AppError(
            "VALIDATION_ERROR",
            "Choose current people from this company.",
            status_code=422,
            field="employee_ids",
        )
    values = [
        {
            "id": uuid7(),
            "company_id": access.company_id,
            "course_id": course,
            "employee_id": person,
            "due_on": body.due_on,
            "status": "not_started",
            "progress": {},
            "assigned_by": access.caller.user_id,
        }
        for course in course_ids
        for person in employee_ids
    ]
    # One row per course and person: assigning the same course twice changes nothing.
    statement = (
        pg_insert(CourseAssignment)
        .values(values)
        .on_conflict_do_nothing(constraint="uq_course_assignments_one_per_person")
        .returning(CourseAssignment.id)
    )
    created = len((await access.db.execute(statement)).all())
    await access.audit(
        "learning.assignments_created",
        entity_type="course_assignment",
        after={
            "courses": len(course_ids),
            "people": len(employee_ids),
            "due_on": body.due_on.isoformat(),
            "created": created,
        },
    )
    await access.db.commit()
    return AssignmentCreatedOut(created=created, already_assigned=len(values) - created)


@router.get("/learning/assignments/own", response_model=list[CourseAssignmentOut])
async def own_assignments(access: OwnReads) -> list[CourseAssignmentOut]:
    if access.employee_id is None:
        return []
    rows = (
        await access.db.execute(
            select(CourseAssignment, Course)
            .join(Course, Course.id == CourseAssignment.course_id)
            .where(
                CourseAssignment.company_id == access.company_id,
                CourseAssignment.employee_id == access.employee_id,
                Course.published.is_(True),
            )
            .order_by(CourseAssignment.due_on, Course.title)
        )
    ).all()
    return [service.assignment_out(row, course) for row, course in rows]


@router.get("/learning/assignments/{assignment_id}", response_model=AssignmentDetailOut)
async def assignment_detail(assignment_id: uuid.UUID, access: OwnReads) -> AssignmentDetailOut:
    row, course = await _own(access, assignment_id)
    return AssignmentDetailOut(
        assignment=service.assignment_out(row, course),
        course=service.learner_out(course),
    )


@router.post("/learning/assignments/{assignment_id}/progress", response_model=CourseAssignmentOut)
async def save_progress(
    assignment_id: uuid.UUID, body: ProgressIn, access: OwnWrites
) -> CourseAssignmentOut:
    row, course = await _own(access, assignment_id, lock=True)
    if body.section >= len(course.sections):
        raise AppError(
            "VALIDATION_ERROR",
            "That section is not in this course.",
            status_code=422,
            field="section",
        )
    row.progress = {**row.progress, "section": body.section}
    if row.status == "not_started":
        row.status = "in_progress"
    await access.db.flush()
    await access.db.commit()
    return service.assignment_out(row, course)


@router.post("/learning/assignments/{assignment_id}/quiz", response_model=QuizResultOut)
async def submit_check(
    assignment_id: uuid.UUID, body: QuizAnswersIn, access: OwnWrites
) -> QuizResultOut:
    row, course = await _own(access, assignment_id, lock=True)
    service.check_answers_fit(body.answers, course)
    score, results = service.score_check(body.answers, course)
    best = max(score, row.quiz_score or 0)
    row.quiz_score = best
    if row.status == "not_started":
        row.status = "in_progress"
    await access.db.flush()
    await access.db.commit()
    # This attempt's result is shown; only the best score decides whether the course completes.
    return QuizResultOut(
        score=score,
        passed=score >= course.pass_mark,
        pass_mark=course.pass_mark,
        best_score=best,
        results=results,
    )


@router.post("/learning/assignments/{assignment_id}/complete", response_model=CourseAssignmentOut)
async def complete_course(assignment_id: uuid.UUID, access: OwnWrites) -> CourseAssignmentOut:
    row, course = await _own(access, assignment_id, lock=True)
    if row.quiz_score is None or row.quiz_score < course.pass_mark:
        raise ConflictError("Pass the check before completing this course.")
    if row.status != "completed":
        row.status = "completed"
        row.completed_at = datetime.now(UTC)
        await access.audit(
            "learning.course_completed",
            entity_type="course_assignment",
            entity_id=row.id,
            after={"score": row.quiz_score},
        )
    await access.db.flush()
    await access.db.commit()
    return service.assignment_out(row, course)
