"""Shapes course rows for learners and editors, and scores a check (plan 8.14).

The pass rule lives here so the router and the tests share one definition: a check is passed when
the score is at least the course's pass mark, as a whole percentage.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.core.errors import AppError, NotFoundError
from app.modules.learning.models import Course, CourseAssignment
from app.modules.learning.schemas import (
    CourseAdminOut,
    CourseAssignmentOut,
    CourseCardOut,
    CourseOut,
    QuestionAdminOut,
    QuestionOut,
    QuestionResultOut,
    SectionOut,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def questions_of(course: Course) -> list[dict[str, Any]]:
    return [dict(question) for question in course.quiz.get("questions", [])]


def sections_of(course: Course) -> list[SectionOut]:
    return [SectionOut(**section) for section in course.sections]


def admin_out(course: Course) -> CourseAdminOut:
    return CourseAdminOut(
        id=course.id,
        slug=course.slug,
        title=course.title,
        summary=course.summary,
        duration_minutes=course.duration_minutes,
        audience=course.audience,
        sections=sections_of(course),
        questions=[QuestionAdminOut(**question) for question in questions_of(course)],
        pass_mark=course.pass_mark,
        source_title=course.source_title,
        source_publisher=course.source_publisher,
        source_url=course.source_url,
        source_updated_on=course.source_updated_on,
        content_reviewed_on=course.content_reviewed_on,
        licence_note=course.licence_note,
        published=course.published,
        version=course.version,
    )


def learner_out(course: Course) -> CourseOut:
    return CourseOut(
        id=course.id,
        slug=course.slug,
        title=course.title,
        summary=course.summary,
        duration_minutes=course.duration_minutes,
        audience=course.audience,
        sections=sections_of(course),
        # Options only: a learner sees the answer after submitting the check, never before.
        questions=[
            QuestionOut(prompt=question["prompt"], options=question["options"])
            for question in questions_of(course)
        ],
        pass_mark=course.pass_mark,
        source_title=course.source_title,
        source_publisher=course.source_publisher,
        source_url=course.source_url,
        source_updated_on=course.source_updated_on,
        content_reviewed_on=course.content_reviewed_on,
        licence_note=course.licence_note,
        version=course.version,
    )


def card_out(course: Course) -> CourseCardOut:
    return CourseCardOut(
        id=course.id,
        slug=course.slug,
        title=course.title,
        summary=course.summary,
        duration_minutes=course.duration_minutes,
        audience=course.audience,
        section_count=len(course.sections),
        question_count=len(questions_of(course)),
        source_title=course.source_title,
        content_reviewed_on=course.content_reviewed_on,
    )


def assignment_out(row: CourseAssignment, course: Course) -> CourseAssignmentOut:
    score = row.quiz_score
    return CourseAssignmentOut(
        id=row.id,
        course_id=course.id,
        slug=course.slug,
        title=course.title,
        summary=course.summary,
        duration_minutes=course.duration_minutes,
        section_count=len(course.sections),
        question_count=len(questions_of(course)),
        pass_mark=course.pass_mark,
        due_on=row.due_on,
        status=row.status,
        section=int(row.progress.get("section", 0)),
        quiz_score=score,
        passed=score is not None and score >= course.pass_mark,
        completed_at=row.completed_at,
    )


def check_answers_fit(answers: list[int], course: Course) -> None:
    """Refuses unless there is one answer per question, each one of that question's options."""
    questions = questions_of(course)
    if len(answers) != len(questions):
        raise AppError(
            "VALIDATION_ERROR",
            f"Answer all {len(questions)} questions.",
            status_code=422,
            field="answers",
        )
    for given, question in zip(answers, questions, strict=True):
        if not 0 <= given < len(question["options"]):
            raise AppError(
                "VALIDATION_ERROR",
                "Choose one of the options for each question.",
                status_code=422,
                field="answers",
            )


def score_check(answers: list[int], course: Course) -> tuple[int, list[QuestionResultOut]]:
    """The whole-percentage score, and each question's result with the right option and why."""
    questions = questions_of(course)
    results: list[QuestionResultOut] = []
    correct = 0
    for given, question in zip(answers, questions, strict=True):
        right = int(question["answer"])
        is_right = given == right
        correct += 1 if is_right else 0
        results.append(
            QuestionResultOut(
                correct=is_right,
                correct_option=right,
                explanation=str(question["explanation"]),
            )
        )
    return round(100 * correct / len(questions)), results


async def course_or_404(
    db: AsyncSession, course_id: uuid.UUID, *, published_only: bool = True
) -> Course:
    query = select(Course).where(Course.id == course_id)
    if published_only:
        query = query.where(Course.published.is_(True))
    row = (await db.execute(query)).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    return row
