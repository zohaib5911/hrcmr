"""Scoped work log, same-day self-service and reasoned administrative corrections."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date  # noqa: TC003
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.core.errors import AppError, NotFoundError
from app.core.rbac_matrix import Scope
from app.modules.attendance.router import _company
from app.modules.employees.models import Employee, EmployeeResponsibility
from app.modules.rbac.deps import Access, require
from app.modules.work_log.models import WorkLogEntry
from app.modules.work_log.schemas import (
    OwnResponsibility,
    WorkLogCorrect,
    WorkLogEdit,
    WorkLogIn,
    WorkLogOut,
    WorkLogPage,
    WorkLogRemove,
)
from app.modules.work_log.service import (
    apply,
    audit_snapshot,
    locked_entry,
    now,
    out,
    own_employee,
    revision,
    snapshot,
    today,
)

router = APIRouter(prefix="/work-log", tags=["work-log"])
Reads = Annotated[Access, Depends(require("work_log.entry.read"))]
OwnWrites = Annotated[Access, Depends(require("work_log.entry.write_own"))]
Corrects = Annotated[Access, Depends(require("work_log.entry.correct"))]


async def _list(
    access: Access,
    start: date,
    end: date,
    employee_id: uuid.UUID | None,
    search: str,
    show_removed: bool,
    show_archived: bool,
    offset: int,
    limit: int,
    *,
    own: bool,
) -> WorkLogPage:
    if end < start or (end - start).days > 366:
        raise AppError("VALIDATION_ERROR", "Choose a range of up to one year.", status_code=422)
    query = (
        select(WorkLogEntry, Employee)
        .join(Employee, Employee.id == WorkLogEntry.employee_id)
        .where(WorkLogEntry.date >= start, WorkLogEntry.date <= end)
    )
    if own or access.scope is Scope.OWN:
        ids = [access.employee_id] if access.employee_id else []
        query = query.where(WorkLogEntry.employee_id.in_(ids))
    elif access.scope is Scope.REPORTS:
        ids = (
            list(await access.reports.reports_of(access.employee_id)) if access.employee_id else []
        )
        query = query.where(WorkLogEntry.employee_id.in_(ids))
    if employee_id is not None:
        if not await access.can_reach(employee_id):
            raise NotFoundError
        query = query.where(WorkLogEntry.employee_id == employee_id)
    if not show_removed:
        query = query.where(WorkLogEntry.removed_at.is_(None))
    if not show_archived:
        query = query.where(Employee.status != "archived")
    if search.strip():
        term = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(
            WorkLogEntry.description.ilike(f"%{term}%")
            | WorkLogEntry.responsibility_text.ilike(f"%{term}%")
            | (Employee.first_name + " " + Employee.last_name).ilike(f"%{term}%")
            | Employee.employee_number.ilike(f"%{term}%")
        )
    summary = query.with_only_columns(
        WorkLogEntry.id, WorkLogEntry.hours, WorkLogEntry.employee_id
    ).subquery()
    count, hours, people = (
        await access.db.execute(
            select(
                func.count(),
                func.coalesce(func.sum(summary.c.hours), 0),
                func.count(func.distinct(summary.c.employee_id)),
            ).select_from(summary)
        )
    ).one()
    rows = (
        await access.db.execute(
            query.order_by(WorkLogEntry.date.desc(), WorkLogEntry.from_time, WorkLogEntry.id)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    on = await today(access)
    company = await _company(access)
    return WorkLogPage(
        items=[out(r, e, access, on) for r, e in rows],
        total=count,
        hours=Decimal(str(hours)),
        employees=people,
        next_offset=offset + limit if offset + len(rows) < count else None,
        timezone=company.timezone,
        today=on,
    )


@router.get("", response_model=WorkLogPage)
async def entries(
    access: Reads,
    start: date,
    end: date,
    employee_id: uuid.UUID | None = None,
    search: Annotated[str, Query(max_length=100)] = "",
    show_removed: bool = False,
    show_archived: bool = False,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> WorkLogPage:
    return await _list(
        access,
        start,
        end,
        employee_id,
        search,
        show_removed,
        show_archived,
        offset,
        limit,
        own=False,
    )


@router.get("/own", response_model=WorkLogPage)
async def own_entries(
    access: Reads,
    start: date,
    end: date,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> WorkLogPage:
    return await _list(access, start, end, None, "", False, True, offset, limit, own=True)


@router.get("/own/responsibilities", response_model=list[OwnResponsibility])
async def own_responsibilities(access: Reads) -> list[OwnResponsibility]:
    if access.employee_id is None:
        return []
    rows = (
        await access.db.execute(
            select(EmployeeResponsibility)
            .where(EmployeeResponsibility.employee_id == access.employee_id)
            .order_by(EmployeeResponsibility.sort, EmployeeResponsibility.id)
        )
    ).scalars()
    return [OwnResponsibility(id=r.id, text=r.text) for r in rows]


@router.post("/own", response_model=WorkLogOut, status_code=201)
async def add_own_entry(body: WorkLogIn, access: OwnWrites) -> WorkLogOut:
    employee = await own_employee(access)
    row = await apply(access, employee, body, own=True)
    await access.audit(
        "work_log.entry_created",
        entity_type="employee",
        entity_id=employee.id,
        after=audit_snapshot(row),
    )
    result = out(row, employee, access, await today(access))
    await access.db.commit()
    return result


@router.patch("/own/{entry_id}", response_model=WorkLogOut)
async def edit_own_entry(entry_id: uuid.UUID, body: WorkLogEdit, access: OwnWrites) -> WorkLogOut:
    row, employee = await locked_entry(access, entry_id, own=True)
    revision(row, body.revision)
    before = audit_snapshot(row)
    row = await apply(access, employee, body, row, own=True)
    await access.audit(
        "work_log.entry_updated",
        entity_type="employee",
        entity_id=employee.id,
        before=before,
        after={**audit_snapshot(row), "content_reviewed": True},
    )
    result = out(row, employee, access, await today(access))
    await access.db.commit()
    return result


@router.post("/{entry_id}/correct", response_model=WorkLogOut)
async def correct_entry(entry_id: uuid.UUID, body: WorkLogCorrect, access: Corrects) -> WorkLogOut:
    row, employee = await locked_entry(access, entry_id)
    revision(row, body.revision)
    before = audit_snapshot(row)
    if row.corrected_from is None:
        row.corrected_from = snapshot(row)
    row = await apply(access, employee, body, row)
    await access.audit(
        "work_log.entry_corrected",
        entity_type="employee",
        entity_id=employee.id,
        before=before,
        after=audit_snapshot(row),
        reason=body.reason,
    )
    result = out(row, employee, access, await today(access))
    await access.db.commit()
    return result


@router.post("/{entry_id}/remove", response_model=WorkLogOut)
async def remove_entry(entry_id: uuid.UUID, body: WorkLogRemove, access: Corrects) -> WorkLogOut:
    row, employee = await locked_entry(access, entry_id)
    revision(row, body.revision)
    if row.removed_at is None:
        row.removed_at, row.removed_by = now(), access.caller.user_id
        await access.db.flush()
        await access.audit(
            "work_log.entry_removed",
            entity_type="employee",
            entity_id=employee.id,
            before=audit_snapshot(row),
            reason=body.reason,
        )
    result = out(row, employee, access, await today(access))
    await access.db.commit()
    return result
