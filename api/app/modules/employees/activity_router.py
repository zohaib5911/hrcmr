"""The employee's audit trail (T6.8), including their attached files."""

from __future__ import annotations

import uuid  # noqa: TC003
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select, tuple_

from app.modules.audit.models import AuditEvent
from app.modules.audit.router import MAX_PAGE, _decode, _encode, _filtered, _out
from app.modules.audit.schemas import AuditPage
from app.modules.employees.router import _employee
from app.modules.files.models import File
from app.modules.rbac.deps import Access, require

router = APIRouter(tags=["employees"])
Reads = Annotated[Access, Depends(require("compliance.audit.read"))]


@router.get("/employees/{employee_id}/activity", response_model=AuditPage)
async def employee_activity(
    employee_id: uuid.UUID,
    access: Reads,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 50,
) -> AuditPage:
    await _employee(access, employee_id)
    files = select(File.id).where(File.owner_type == "employee", File.owner_id == employee_id)
    query = _filtered(
        access,
        action=None,
        entity_type=None,
        entity_id=None,
        actor_user_id=None,
        since=None,
        until=None,
    ).where(
        or_(
            (AuditEvent.entity_type == "employee") & (AuditEvent.entity_id == employee_id),
            (AuditEvent.entity_type == "file") & AuditEvent.entity_id.in_(files),
        )
    )
    if cursor:
        stamp, ident = _decode(cursor)
        query = query.where(tuple_(AuditEvent.created_at, AuditEvent.id) < (stamp, ident))
    result = await access.db.execute(
        query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(limit + 1)
    )
    rows = result.all()
    page = rows[:limit]
    last = page[-1][0] if page else None
    return AuditPage(
        items=[_out(event, first, last_name) for event, first, last_name in page],
        next_cursor=_encode(last.created_at, last.id)
        if last is not None and len(rows) > limit
        else None,
    )
