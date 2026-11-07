"""The org chart tree and the hierarchy levels (plan 8.13).

The tree is built from each person's Reporting Authority on the assignment in force today (the same
rule as the reports graph, plan 6.3). Hierarchy levels are labels only.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, func, or_, select

from app.core.errors import NotFoundError
from app.db.rtw import employee_rtw_status
from app.modules.companies.models import Department, Designation
from app.modules.employees.models import Employee, EmployeeAssignment
from app.modules.organogram.models import OrganogramLevel
from app.modules.organogram.schemas import OrgPerson

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

DEFAULT_LEVEL = "Director"
# People who are still in the company. Leavers and archived records stay out of the chart.
IN_CHART = ("active", "on_leave")


async def seed_levels(db: AsyncSession, company_id: uuid.UUID) -> None:
    db.add(OrganogramLevel(company_id=company_id, name=DEFAULT_LEVEL, rank=1))
    await db.flush()


@dataclass(frozen=True)
class Member:
    id: uuid.UUID
    name: str
    manager_id: uuid.UUID | None
    job_title: str | None
    department: str | None
    level: str | None
    rtw_status: str | None


def build_tree(members: list[Member]) -> list[OrgPerson]:
    """Each person sits under their Reporting Authority.

    A person with no manager in the chart, and anyone in a loop of managers, starts at the top
    (the ``unassigned`` list). Every person appears exactly once, and a loop cannot hang the walk.
    """
    known = {member.id for member in members}
    manager_of = {
        member.id: member.manager_id
        if member.manager_id in known and member.manager_id != member.id
        else None
        for member in members
    }
    reports: dict[uuid.UUID, list[uuid.UUID]] = {}
    for member in members:
        boss = manager_of[member.id]
        if boss is not None:
            reports.setdefault(boss, []).append(member.id)
    nodes: dict[uuid.UUID, OrgPerson] = {
        member.id: OrgPerson(
            id=member.id,
            name=member.name,
            job_title=member.job_title,
            department=member.department,
            level=member.level,
            rtw_status=member.rtw_status,
            reports=[],
        )
        for member in members
    }
    attached: set[uuid.UUID] = set()
    top: list[OrgPerson] = []

    def attach(root: uuid.UUID) -> None:
        top.append(nodes[root])
        attached.add(root)
        queue = deque([root])
        while queue:
            current = queue.popleft()
            for report in reports.get(current, []):
                if report not in attached:
                    attached.add(report)
                    nodes[current].reports.append(nodes[report])
                    queue.append(report)

    for member in members:
        if manager_of[member.id] is None:
            attach(member.id)
    for member in members:
        if member.id not in attached:  # only loops of managers are left
            attach(member.id)
    return top


async def org_chart(db: AsyncSession, company_id: uuid.UUID, *, with_rtw: bool) -> list[OrgPerson]:
    today = func.current_date()
    in_force = and_(
        EmployeeAssignment.employee_id == Employee.id,
        EmployeeAssignment.company_id == company_id,
        EmployeeAssignment.effective_from <= today,
        or_(EmployeeAssignment.ended_at.is_(None), EmployeeAssignment.ended_at > today),
    )
    columns: list[Any] = [
        Employee.id,
        Employee.first_name,
        Employee.last_name,
        EmployeeAssignment.reporting_authority_employee_id,
        Designation.title,
        Department.name,
        OrganogramLevel.name,
    ]
    query = (
        select(*columns)
        .select_from(Employee)
        .outerjoin(EmployeeAssignment, in_force)
        .outerjoin(Designation, Designation.id == EmployeeAssignment.designation_id)
        .outerjoin(Department, Department.id == EmployeeAssignment.department_id)
        .outerjoin(OrganogramLevel, OrganogramLevel.id == EmployeeAssignment.organogram_level_id)
    )
    if with_rtw:
        query = query.add_columns(employee_rtw_status.c.status).outerjoin(
            employee_rtw_status,
            and_(
                employee_rtw_status.c.employee_id == Employee.id,
                employee_rtw_status.c.company_id == company_id,
            ),
        )
    query = query.where(Employee.company_id == company_id, Employee.status.in_(IN_CHART)).order_by(
        Employee.last_name, Employee.first_name, Employee.id
    )
    members = [
        Member(
            id=row[0],
            name=f"{row[1]} {row[2]}".strip(),
            manager_id=row[3],
            job_title=row[4],
            department=row[5],
            level=row[6],
            rtw_status=row[7] if with_rtw else None,
        )
        for row in (await db.execute(query)).all()
    ]
    return build_tree(members)


async def level_or_404(
    db: AsyncSession, company_id: uuid.UUID, level_id: uuid.UUID, *, lock: bool = False
) -> OrganogramLevel:
    query = select(OrganogramLevel).where(
        OrganogramLevel.id == level_id, OrganogramLevel.company_id == company_id
    )
    if lock:
        query = query.with_for_update()
    row = (await db.execute(query)).scalar_one_or_none()
    if row is None:
        raise NotFoundError()
    return row


async def name_taken(
    db: AsyncSession, company_id: uuid.UUID, name: str, *, except_id: uuid.UUID | None = None
) -> bool:
    query = select(OrganogramLevel.id).where(
        OrganogramLevel.company_id == company_id,
        func.lower(OrganogramLevel.name) == name.lower(),
    )
    if except_id is not None:
        query = query.where(OrganogramLevel.id != except_id)
    return (await db.execute(query.limit(1))).first() is not None


async def next_rank(db: AsyncSession, company_id: uuid.UUID) -> int:
    top = (
        await db.execute(
            select(func.max(OrganogramLevel.rank)).where(OrganogramLevel.company_id == company_id)
        )
    ).scalar_one()
    return (top or 0) + 1


async def level_in_use(db: AsyncSession, company_id: uuid.UUID, level_id: uuid.UUID) -> bool:
    """True if any assignment, current or past, points at the level."""
    found = (
        await db.execute(
            select(EmployeeAssignment.id)
            .where(
                EmployeeAssignment.company_id == company_id,
                EmployeeAssignment.organogram_level_id == level_id,
            )
            .limit(1)
        )
    ).first()
    return found is not None
