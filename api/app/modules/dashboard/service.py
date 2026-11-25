"""The dashboard cards and the set-up checklist (plan 8.2).

A card is built only when the caller may read its data for the whole company (scope ALL), or, for
the personal learning card, only from the caller's own assignments. Every figure comes from the
existing module's table or view; nothing is cached across people.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.rbac_matrix import Scope, scope_for
from app.db.ids import uuid7
from app.db.rtw import employee_rtw_status
from app.modules.companies.models import Company, Department, KeyPerson, Location
from app.modules.dashboard.models import OnboardingDismissal
from app.modules.dashboard.schemas import (
    ApprovalsCardOut,
    AttentionItemOut,
    ChecklistItemOut,
    ChecklistOut,
    DashboardOut,
    DistributionCardOut,
    DistributionRowOut,
    EmployeesCardOut,
    LearningCardOut,
    MyLearningCardOut,
    OffCardOut,
    RecruitmentCardOut,
    RtwCardOut,
)
from app.modules.employees.models import Employee, EmployeeAssignment
from app.modules.learning import report as learning_report
from app.modules.learning.models import CourseAssignment
from app.modules.leave.request_models import LeaveRequest
from app.modules.recruitment.models import Candidate
from app.modules.rtw.models import RTWCheck

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.rbac.deps import Access

CURRENT = ("active", "on_leave")


def company_wide(role: str, permission: str) -> bool:
    return scope_for(role, permission) is Scope.ALL


async def _employees(db: AsyncSession, company_id: uuid.UUID) -> EmployeesCardOut:
    rows = (
        await db.execute(
            select(Employee.status, func.count())
            .where(Employee.company_id == company_id, Employee.status.in_(CURRENT))
            .group_by(Employee.status)
        )
    ).all()
    counts: dict[str, int] = dict(rows)
    return EmployeesCardOut(active=counts.get("active", 0), on_leave=counts.get("on_leave", 0))


async def _rtw(db: AsyncSession, company_id: uuid.UUID) -> RtwCardOut:
    status = employee_rtw_status.c.status
    rows = (
        await db.execute(
            select(status, func.count())
            .select_from(employee_rtw_status)
            .join(Employee, Employee.id == employee_rtw_status.c.employee_id)
            .where(Employee.company_id == company_id, Employee.status.in_(CURRENT))
            .group_by(status)
        )
    ).all()
    counts: dict[str, int] = dict(rows)
    total = sum(counts.values())
    verified = counts.get("verified", 0)
    return RtwCardOut(
        checked=total,
        verified=verified,
        expiring=counts.get("expiring", 0),
        expired=counts.get("expired", 0),
        evidence_missing=counts.get("evidence_missing", 0),
        not_recorded=counts.get("not_recorded", 0),
        coverage_percent=round(100 * verified / total) if total else 0,
    )


async def _off(db: AsyncSession, company_id: uuid.UUID) -> OffCardOut:
    on_leave = and_(Employee.company_id == company_id, Employee.status == "on_leave")
    total = (
        await db.execute(select(func.count()).select_from(Employee).where(on_leave))
    ).scalar_one()
    names = (
        await db.execute(
            select(Employee.first_name, Employee.last_name)
            .where(on_leave)
            .order_by(Employee.last_name, Employee.first_name)
            .limit(5)
        )
    ).all()
    return OffCardOut(count=total, names=[f"{first} {last}".strip() for first, last in names])


async def _approvals(db: AsyncSession, company_id: uuid.UUID) -> ApprovalsCardOut:
    pending = (
        await db.execute(
            select(func.count())
            .select_from(LeaveRequest)
            .where(LeaveRequest.company_id == company_id, LeaveRequest.status == "pending")
        )
    ).scalar_one()
    return ApprovalsCardOut(pending=pending)


async def _distribution(
    db: AsyncSession, company_id: uuid.UUID, today: date
) -> DistributionCardOut:
    in_force = and_(
        EmployeeAssignment.employee_id == Employee.id,
        EmployeeAssignment.company_id == company_id,
        EmployeeAssignment.effective_from <= today,
        or_(EmployeeAssignment.ended_at.is_(None), EmployeeAssignment.ended_at > today),
    )
    rows = (
        await db.execute(
            select(Department.name, func.count())
            .select_from(Employee)
            .outerjoin(EmployeeAssignment, in_force)
            .outerjoin(Department, Department.id == EmployeeAssignment.department_id)
            .where(Employee.company_id == company_id, Employee.status.in_(CURRENT))
            .group_by(Department.name)
            .order_by(Department.name)
        )
    ).all()
    return DistributionCardOut(
        rows=[
            DistributionRowOut(department=name or "Unassigned", headcount=count)
            for name, count in rows
        ]
    )


async def _learning(db: AsyncSession, company_id: uuid.UUID, today: date) -> LearningCardOut:
    overdue = (
        await db.execute(
            select(func.count())
            .select_from(CourseAssignment)
            .where(
                CourseAssignment.company_id == company_id,
                learning_report.effective_status(today) == "overdue",
            )
        )
    ).scalar_one()
    return LearningCardOut(overdue=overdue)


async def _my_learning(
    db: AsyncSession, company_id: uuid.UUID, employee_id: uuid.UUID, today: date
) -> MyLearningCardOut:
    status_now = learning_report.effective_status(today)
    rows = (
        await db.execute(
            select(status_now, func.count())
            .where(
                CourseAssignment.company_id == company_id,
                CourseAssignment.employee_id == employee_id,
            )
            .group_by(status_now)
        )
    ).all()
    counts: dict[str, int] = dict(rows)
    open_count = sum(counts.get(s, 0) for s in ("not_started", "in_progress", "overdue"))
    return MyLearningCardOut(open=open_count, overdue=counts.get("overdue", 0))


async def _recruitment(db: AsyncSession, company_id: uuid.UUID) -> RecruitmentCardOut:
    rows = (
        await db.execute(
            select(Candidate.first_name, Candidate.last_name)
            .where(Candidate.company_id == company_id)
            .order_by(Candidate.created_at.desc())
            .limit(5)
        )
    ).all()
    return RecruitmentCardOut(latest=[f"{first} {last}".strip() for first, last in rows])


def _attention(
    approvals: ApprovalsCardOut | None,
    rtw: RtwCardOut | None,
    learning: LearningCardOut | None,
) -> list[AttentionItemOut]:
    items: list[AttentionItemOut] = []
    if learning is not None and learning.overdue:
        items.append(
            AttentionItemOut(label="Courses overdue", count=learning.overdue, link="/learning")
        )
    if approvals is not None and approvals.pending:
        items.append(
            AttentionItemOut(
                label="Leave requests to decide", count=approvals.pending, link="/leave"
            )
        )
    if rtw is not None and rtw.expired + rtw.expiring:
        items.append(
            AttentionItemOut(
                label="Right to Work to check",
                count=rtw.expired + rtw.expiring,
                link="/employees?rtw=Expiring",
            )
        )
    return items


def _status_line(items: list[AttentionItemOut]) -> str:
    total = sum(item.count for item in items)
    if total == 0:
        return "Nothing needs your attention today"
    return "1 item needs your attention" if total == 1 else f"{total} items need your attention"


async def dashboard(access: Access) -> DashboardOut:
    db, company_id, role = access.db, access.company_id, access.role
    today = await access.reports.today()  # the company's date, as the permissions use
    employees = (
        await _employees(db, company_id) if company_wide(role, "employee.profile.read") else None
    )
    rtw = await _rtw(db, company_id) if company_wide(role, "employee.rtw.read") else None
    off = await _off(db, company_id) if company_wide(role, "employee.profile.read") else None
    approvals = (
        await _approvals(db, company_id) if company_wide(role, "leave.request.approve") else None
    )
    distribution = (
        await _distribution(db, company_id, today)
        if company_wide(role, "employee.profile.read")
        else None
    )
    learning = (
        await _learning(db, company_id, today)
        if company_wide(role, "learning.assignment.read")
        else None
    )
    recruitment = (
        await _recruitment(db, company_id)
        if company_wide(role, "recruitment.candidate.read")
        else None
    )
    my_learning = None
    if (
        access.employee_id is not None
        and scope_for(role, "learning.assignment.read_own") is not None
    ):
        my_learning = await _my_learning(db, company_id, access.employee_id, today)
    items = _attention(approvals, rtw, learning)
    return DashboardOut(
        first_name=access.caller.user.first_name,
        status_line=_status_line(items),
        needs_attention=items[:5],
        employees=employees,
        rtw=rtw,
        off_today=off,
        approvals=approvals,
        distribution=distribution,
        learning=learning,
        my_learning=my_learning,
        recruitment=recruitment,
    )


async def _count(db: AsyncSession, statement: Any) -> int:
    return int((await db.execute(statement)).scalar_one())


async def checklist(access: Access) -> ChecklistOut:
    db, company_id = access.db, access.company_id
    company = (await db.execute(select(Company).where(Company.id == company_id))).scalar_one()
    departments = await _count(db, select(func.count()).select_from(Department))
    locations = await _count(db, select(func.count()).select_from(Location))
    employees = await _count(db, select(func.count()).select_from(Employee))
    rtw_checks = await _count(db, select(func.count()).select_from(RTWCheck))
    key_people = await _count(
        db, select(func.count()).select_from(KeyPerson).where(KeyPerson.archived_at.is_(None))
    )
    items = [
        ChecklistItemOut(
            key="company_details",
            label="Add your company details",
            done=bool(company.registered_number and company.contact_phone),
        ),
        ChecklistItemOut(
            key="departments_locations",
            label="Add departments and locations",
            done=departments > 0 and locations > 0,
        ),
        ChecklistItemOut(key="first_employee", label="Add your first employee", done=employees > 0),
        ChecklistItemOut(
            key="first_rtw", label="Record a first Right to Work check", done=rtw_checks > 0
        ),
        ChecklistItemOut(key="key_personnel", label="Add key personnel", done=key_people > 0),
    ]
    done = sum(1 for item in items if item.done)
    dismissed = (
        await db.execute(
            select(OnboardingDismissal.id)
            .where(
                OnboardingDismissal.company_id == company_id,
                OnboardingDismissal.user_id == access.caller.user_id,
            )
            .limit(1)
        )
    ).first() is not None
    return ChecklistOut(
        visible=not dismissed and done < len(items),
        done=done,
        total=len(items),
        items=items,
    )


async def dismiss(access: Access) -> None:
    statement = (
        pg_insert(OnboardingDismissal)
        .values(
            id=uuid7(),
            company_id=access.company_id,
            user_id=access.caller.user_id,
            dismissed_at=datetime.now(UTC),
        )
        .on_conflict_do_nothing(constraint="uq_onboarding_dismissals_company_user")
    )
    await access.db.execute(statement)
    await access.db.commit()
