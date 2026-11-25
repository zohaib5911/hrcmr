"""The assignment report, its summary, and who a new assignment covers (plan 6.9, 8.14).

A status is "overdue" when its due day has passed and it is not completed. The overdue job writes
that status once a day; the report computes it too, so a late job never hides a late course.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date  # noqa: TC003
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, case, func, or_, select

from app.core.errors import AppError
from app.modules.companies.models import Department
from app.modules.employees.models import Employee, EmployeeAssignment
from app.modules.learning.models import Course, CourseAssignment
from app.modules.learning.schemas import LearningSummaryOut, ReportRowOut

if TYPE_CHECKING:
    from sqlalchemy import Select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.learning.schemas import CourseAssignmentIn

CURRENT = ("active", "on_leave")  # people who can be assigned a course
OPEN = ("not_started", "in_progress")


def effective_status(today: date) -> Any:
    """The status a person sees today (the company's today): an open course past its due day is
    overdue."""
    return case(
        (
            and_(
                CourseAssignment.status.in_(OPEN),
                CourseAssignment.due_on < today,
            ),
            "overdue",
        ),
        else_=CourseAssignment.status,
    )


def in_force(company_id: uuid.UUID, today: date) -> Any:
    """The employee's assignment in force today (the rule the reports graph and org chart use)."""
    return and_(
        EmployeeAssignment.employee_id == Employee.id,
        EmployeeAssignment.company_id == company_id,
        EmployeeAssignment.effective_from <= today,
        or_(EmployeeAssignment.ended_at.is_(None), EmployeeAssignment.ended_at > today),
    )


def report_query(
    company_id: uuid.UUID,
    *,
    course_id: uuid.UUID | None,
    department_id: uuid.UUID | None,
    status: str | None,
    search: str,
    today: date,
) -> Select[Any]:
    status_now = effective_status(today)
    query = (
        select(
            CourseAssignment,
            Course,
            Employee.first_name,
            Employee.last_name,
            Department.name,
            status_now.label("status_now"),
        )
        .join(Course, Course.id == CourseAssignment.course_id)
        .join(Employee, Employee.id == CourseAssignment.employee_id)
        .outerjoin(EmployeeAssignment, in_force(company_id, today))
        .outerjoin(Department, Department.id == EmployeeAssignment.department_id)
        .where(CourseAssignment.company_id == company_id)
    )
    if course_id is not None:
        query = query.where(CourseAssignment.course_id == course_id)
    if department_id is not None:
        query = query.where(Department.id == department_id)
    if status is not None:
        query = query.where(status_now == status)
    if search.strip():
        name = func.lower(Employee.first_name + " " + Employee.last_name)
        query = query.where(name.contains(search.strip().lower(), autoescape=True))
    return query.order_by(
        Employee.last_name, Employee.first_name, Course.title, CourseAssignment.id
    )


def report_row(row: Any) -> ReportRowOut:
    assignment, course, first, last, department, status_now = row
    return ReportRowOut(
        id=assignment.id,
        course_id=course.id,
        course_title=course.title,
        employee_id=assignment.employee_id,
        employee_name=f"{first} {last}".strip(),
        department=department,
        due_on=assignment.due_on,
        status=status_now,
        quiz_score=assignment.quiz_score,
        completed_at=assignment.completed_at,
    )


async def summary(db: AsyncSession, company_id: uuid.UUID, today: date) -> LearningSummaryOut:
    status_now = effective_status(today)
    rows = (
        await db.execute(
            select(status_now, func.count())
            .where(CourseAssignment.company_id == company_id)
            .group_by(status_now)
        )
    ).all()
    counts: dict[str, int] = dict(rows)
    return LearningSummaryOut(
        assignments=sum(counts.values()),
        not_started=counts.get("not_started", 0),
        in_progress=counts.get("in_progress", 0),
        completed=counts.get("completed", 0),
        overdue=counts.get("overdue", 0),
    )


async def people_for(
    db: AsyncSession, company_id: uuid.UUID, body: CourseAssignmentIn, today: date
) -> list[uuid.UUID]:
    """The current staff a new assignment covers. It is all checked before any row is written."""
    if body.scope == "everyone":
        query = select(Employee.id).where(
            Employee.company_id == company_id, Employee.status.in_(CURRENT)
        )
        return list((await db.execute(query)).scalars().all())
    if body.scope == "departments":
        wanted = set(body.department_ids)
        if not wanted:
            raise AppError(
                "VALIDATION_ERROR",
                "Choose at least one department.",
                status_code=422,
                field="department_ids",
            )
        found = (
            (
                await db.execute(
                    select(Department.id).where(
                        Department.id.in_(wanted), Department.company_id == company_id
                    )
                )
            )
            .scalars()
            .all()
        )
        if len(set(found)) != len(wanted):
            raise AppError(
                "VALIDATION_ERROR",
                "Choose departments from this company.",
                status_code=422,
                field="department_ids",
            )
        query = (
            select(Employee.id)
            .join(EmployeeAssignment, in_force(company_id, today))
            .where(
                Employee.company_id == company_id,
                Employee.status.in_(CURRENT),
                EmployeeAssignment.department_id.in_(wanted),
            )
        )
        return list((await db.execute(query)).scalars().all())
    wanted_people = set(body.employee_ids)
    if not wanted_people:
        raise AppError(
            "VALIDATION_ERROR",
            "Choose at least one person.",
            status_code=422,
            field="employee_ids",
        )
    found_people = (
        (
            await db.execute(
                select(Employee.id).where(
                    Employee.id.in_(wanted_people),
                    Employee.company_id == company_id,
                    Employee.status.in_(CURRENT),
                )
            )
        )
        .scalars()
        .all()
    )
    if len(set(found_people)) != len(wanted_people):
        raise AppError(
            "VALIDATION_ERROR",
            "Choose current people from this company.",
            status_code=422,
            field="employee_ids",
        )
    return list(wanted_people)
