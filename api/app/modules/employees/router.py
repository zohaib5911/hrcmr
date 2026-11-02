"""Employees (plan.md 8.3): the list and its summary. The record itself, creating one and the
profile come in T6.2 and T6.3. A person sees what their permission reaches: everyone, their reports,
or only themselves."""

from __future__ import annotations

import uuid  # noqa: TC003  (FastAPI reads the annotations at run time)
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select

from app.core.rbac_matrix import Scope
from app.modules.companies.models import Department, Designation
from app.modules.employees.models import Employee, EmployeeAssignment
from app.modules.employees.schemas import EmployeeList, EmployeeRow, EmployeeSummary, Status
from app.modules.rbac.deps import Access, require

router = APIRouter(tags=["employees"])

Reads = Annotated[Access, Depends(require("employee.profile.read"))]
LIMIT = 2000


async def _reachable(access: Access) -> frozenset[uuid.UUID] | None:
    """The employees this person may see: None means everyone."""
    if access.scope is Scope.ALL:
        return None
    mine = {access.employee_id} if access.employee_id else set()
    if access.scope is Scope.REPORTS and access.employee_id:
        mine |= await access.reports.reports_of(access.employee_id)
    return frozenset(mine)


def _like(text_: str) -> str:
    escaped = text_.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@router.get("/employees", response_model=EmployeeList)
async def list_employees(
    access: Reads,
    status: Annotated[Status | None, Query()] = None,
    department_id: Annotated[uuid.UUID | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100, description="Name or number contains.")] = None,
    archived: Annotated[
        bool, Query(description="Include archived records (or, with status=archived, only them).")
    ] = False,
) -> EmployeeList:
    reach = await _reachable(access)
    query = (
        select(Employee, EmployeeAssignment.department_id, Department.name, Designation.title)
        .outerjoin(
            EmployeeAssignment,
            (EmployeeAssignment.employee_id == Employee.id) & EmployeeAssignment.ended_at.is_(None),
        )
        .outerjoin(Department, Department.id == EmployeeAssignment.department_id)
        .outerjoin(Designation, Designation.id == EmployeeAssignment.designation_id)
    )
    if reach is not None:
        query = query.where(Employee.id.in_(reach))
    if status:
        query = query.where(Employee.status == status)
    elif not archived:
        query = query.where(Employee.status != "archived")
    if department_id:
        query = query.where(EmployeeAssignment.department_id == department_id)
    if q and q.strip():
        pattern = _like(q.strip())
        query = query.where(
            or_(
                Employee.employee_number.ilike(pattern, escape="\\"),
                func.regexp_replace(Employee.employee_number, r"\s", "", "g").ilike(
                    _like("".join(q.split())), escape="\\"
                ),
                Employee.first_name.ilike(pattern, escape="\\"),
                Employee.last_name.ilike(pattern, escape="\\"),
                func.concat(Employee.first_name, " ", Employee.last_name).ilike(
                    pattern, escape="\\"
                ),
            )
        )
    total = (
        await access.db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar_one()
    rows = (
        await access.db.execute(
            query.order_by(func.lower(Employee.last_name), func.lower(Employee.first_name)).limit(
                LIMIT
            )
        )
    ).all()
    return EmployeeList(
        employees=[
            EmployeeRow(
                id=e.id,
                employee_number=e.employee_number,
                first_name=e.first_name,
                last_name=e.last_name,
                email=e.email,
                status=e.status,  # type: ignore[arg-type]
                hire_date=e.hire_date,
                department_id=department_id_,
                department=department,
                designation=designation,
                has_photo=e.photo_file_id is not None,
            )
            for e, department_id_, department, designation in rows
        ],
        total=total,
    )


@router.get("/employees/summary", response_model=EmployeeSummary)
async def employee_summary(access: Reads) -> EmployeeSummary:
    reach = await _reachable(access)
    query = select(Employee.status, func.count()).group_by(Employee.status)
    if reach is not None:
        query = query.where(Employee.id.in_(reach))
    counts = dict((await access.db.execute(query)).all())
    live = sum(n for status, n in counts.items() if status != "archived")
    return EmployeeSummary(
        total=live,
        active=counts.get("active", 0),
        on_leave=counts.get("on_leave", 0),
        leavers=counts.get("leaver", 0),
        archived=counts.get("archived", 0),
    )
