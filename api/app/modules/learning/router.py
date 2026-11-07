"""Learning: the course library, assignments, the report, the player and the check (plan 8.14).

Only the person a course is assigned to can see it, record progress, sit the check or complete it.
A check that is below the pass mark never completes a course. The report is for people who may
read every assignment (the company's administrators and auditors), never for an employee.
"""

from __future__ import annotations

import asyncio
import uuid  # noqa: TC003
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

if TYPE_CHECKING:
    from sqlalchemy.engine import CursorResult

from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.rbac_matrix import Scope
from app.db.ids import uuid7
from app.modules.learning import certificates, report, service
from app.modules.learning.models import Course, CourseAssignment
from app.modules.learning.schemas import (
    AssignmentCreatedOut,
    AssignmentDetailOut,
    CourseAssignmentIn,
    CourseAssignmentOut,
    CourseCardOut,
    CourseOut,
    LearningSummaryOut,
    ProgressIn,
    QuizAnswersIn,
    QuizResultOut,
    ReportPageOut,
)
from app.modules.learning.workbook import xlsx_bytes
from app.modules.rbac.deps import Access, require

router = APIRouter(tags=["learning"])
CourseReads = Annotated[Access, Depends(require("learning.course.read"))]
AssignWrites = Annotated[Access, Depends(require("learning.assignment.write"))]
ReportReads = Annotated[Access, Depends(require("learning.assignment.read"))]
OwnReads = Annotated[Access, Depends(require("learning.assignment.read_own"))]
OwnWrites = Annotated[Access, Depends(require("learning.assignment.complete_own"))]

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
Status = Literal["not_started", "in_progress", "completed", "overdue"]


def _company_wide(access: Access) -> None:
    """The report covers the whole company. Someone who may only see their own is refused."""
    if access.scope is not Scope.ALL:
        raise ForbiddenError


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
    # Every person is resolved and checked before a single row is written.
    people = await report.people_for(access.db, access.company_id, body)
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
        for person in people
    ]
    # One row per course and person: assigning the same course twice changes nothing.
    created = 0
    if values:
        statement = pg_insert(CourseAssignment).values(values)
        statement = statement.on_conflict_do_nothing(
            constraint="uq_course_assignments_one_per_person"
        )
        # rowcount is the number of rows actually inserted; the rest already existed.
        result = cast("CursorResult[Any]", await access.db.execute(statement))
        created = result.rowcount
    await access.audit(
        "learning.assignments_created",
        entity_type="course_assignment",
        after={
            "scope": body.scope,
            "courses": len(course_ids),
            "people": len(people),
            "due_on": body.due_on.isoformat(),
            "created": created,
        },
    )
    await access.db.commit()
    return AssignmentCreatedOut(created=created, already_assigned=len(values) - created)


@router.get("/learning/assignments", response_model=ReportPageOut)
async def assignment_report(
    access: ReportReads,
    course_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    status: Status | None = None,
    search: Annotated[str, Query(max_length=200)] = "",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ReportPageOut:
    _company_wide(access)
    query = report.report_query(
        access.company_id,
        course_id=course_id,
        department_id=department_id,
        status=status,
        search=search,
    )
    total = (
        await access.db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar_one()
    rows = (await access.db.execute(query.offset(offset).limit(limit))).all()
    return ReportPageOut(items=[report.report_row(row) for row in rows], total=total)


@router.get("/learning/summary", response_model=LearningSummaryOut)
async def learning_summary(access: ReportReads) -> LearningSummaryOut:
    _company_wide(access)
    return await report.summary(access.db, access.company_id)


@router.get(
    "/learning/assignments.xlsx",
    response_class=Response,
    responses={200: {"content": {XLSX: {}}}},
)
async def assignment_export(
    access: ReportReads,
    course_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    status: Status | None = None,
    search: Annotated[str, Query(max_length=200)] = "",
) -> Response:
    _company_wide(access)
    rows = (
        await access.db.execute(
            report.report_query(
                access.company_id,
                course_id=course_id,
                department_id=department_id,
                status=status,
                search=search,
            )
        )
    ).all()
    values = [
        [
            item.employee_name,
            item.department or "",
            item.course_title,
            item.due_on.isoformat(),
            item.status.replace("_", " ").capitalize(),
            "" if item.quiz_score is None else item.quiz_score,
            item.completed_at.date().isoformat() if item.completed_at else "",
        ]
        for item in (report.report_row(row) for row in rows)
    ]
    content = await asyncio.to_thread(
        xlsx_bytes,
        ["Employee", "Department", "Course", "Due", "Status", "Check score (%)", "Completed"],
        values,
    )
    await access.audit(
        "learning.report_exported",
        entity_type="course_assignment",
        after={"rows": len(values)},
    )
    await access.db.commit()
    return Response(
        content,
        media_type=XLSX,
        headers={
            "Content-Disposition": 'attachment; filename="learning-report.xlsx"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


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
        await certificates.issue(access.db, row, course)
        await access.audit(
            "learning.course_completed",
            entity_type="course_assignment",
            entity_id=row.id,
            after={"score": row.quiz_score},
        )
    await access.db.flush()
    await access.db.commit()
    return service.assignment_out(row, course)
