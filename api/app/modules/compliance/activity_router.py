"""The hub's audit feed and CSV share exactly the same category/date filters."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import or_, tuple_

from app.modules.audit.models import AuditEvent
from app.modules.audit.router import (
    EXPORT_LIMIT,
    MAX_PAGE,
    _decode,
    _encode,
    _filtered,
    _out,
    csv_cell,
)
from app.modules.audit.schemas import AuditPage
from app.modules.compliance.hub_schemas import ActivityCategory  # noqa: TC001
from app.modules.rbac.deps import Access, require

if TYPE_CHECKING:
    from sqlalchemy import Select

router = APIRouter(tags=["compliance-hub"])
Reads = Annotated[Access, Depends(require("compliance.audit.read"))]
Exports = Annotated[Access, Depends(require("compliance.audit.export"))]
PREFIXES = {
    "rtw": ("employee.rtw_",),
    "employees": ("employee.",),
    "attendance": ("attendance.",),
    "documents": (
        "file.",
        "employee.document_",
        "employee.sponsor_document_",
        "compliance_document.",
    ),
    "changes": ("employee.change_", "company.change_"),
}


def _query(
    access: Access, category: ActivityCategory, since: datetime | None, until: datetime | None
) -> Select[AuditEvent, str | None, str | None]:
    query = _filtered(
        access,
        action=None,
        entity_type=None,
        entity_id=None,
        actor_user_id=None,
        since=since,
        until=until,
    )
    if category != "all":
        query = query.where(
            or_(
                *(
                    AuditEvent.action.startswith(prefix, autoescape=True)
                    for prefix in PREFIXES[category]
                )
            )
        )
    return query


@router.get("/compliance/activity", response_model=AuditPage)
async def activity(
    access: Reads,
    category: ActivityCategory = "all",
    since: datetime | None = None,
    until: datetime | None = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 50,
) -> AuditPage:
    query = _query(access, category, since, until)
    if cursor:
        stamp, ident = _decode(cursor)
        query = query.where(tuple_(AuditEvent.created_at, AuditEvent.id) < (stamp, ident))
    rows = (
        await access.db.execute(
            query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(limit + 1)
        )
    ).all()
    page = rows[:limit]
    last = page[-1][0] if page else None
    return AuditPage(
        items=[_out(event, first, surname) for event, first, surname in page],
        next_cursor=_encode(last.created_at, last.id) if last and len(rows) > limit else None,
    )


@router.get("/compliance/activity.csv", response_class=Response)
async def export_activity(
    access: Exports,
    category: ActivityCategory = "all",
    since: datetime | None = None,
    until: datetime | None = None,
) -> Response:
    query = _query(access, category, since, until)
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(["Time (UTC)", "Who", "Action", "What", "Summary", "Reason"])
    written = 0
    last = None
    while written < EXPORT_LIMIT:
        page = query
        if last is not None:
            page = page.where(
                tuple_(AuditEvent.created_at, AuditEvent.id) < (last.created_at, last.id)
            )
        rows = (
            await access.db.execute(
                page.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(
                    min(1000, EXPORT_LIMIT - written)
                )
            )
        ).all()
        if not rows:
            break
        for event, first, surname in rows:
            writer.writerow(
                [
                    csv_cell(value)
                    for value in (
                        event.created_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                        f"{first} {surname}".strip() if first else event.actor_type,
                        event.action,
                        f"{event.entity_type or ''} {event.entity_id or ''}".strip(),
                        event.summary,
                        event.reason,
                    )
                ]
            )
            written += 1
        last = rows[-1][0]
    await access.audit(
        "compliance.activity_exported",
        entity_type="audit_events",
        after={"category": category, "since": since, "until": until},
        summary=f"Exported {written} events",
    )
    await access.db.commit()
    return Response(
        out.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="compliance-activity.csv"',
            "Cache-Control": "private, no-store",
        },
    )
