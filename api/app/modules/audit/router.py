"""Reading the audit trail (plan.md 4.5): ``GET /audit-events`` and its CSV export."""

from __future__ import annotations

import base64
import csv
import io
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select, tuple_

from app.core.errors import AppError
from app.modules.audit.models import AuditEvent
from app.modules.audit.schemas import AuditEventOut, AuditPage
from app.modules.identity.models import User
from app.modules.rbac.deps import Access, require

if TYPE_CHECKING:
    from sqlalchemy import Select
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["audit"])

MAX_PAGE = 200
EXPORT_LIMIT = 50_000
_EXPORT_PAGE = 1000


def _encode(created_at: datetime, event_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{event_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        stamp, _, ident = base64.urlsafe_b64decode(cursor.encode()).decode().partition("|")
        return datetime.fromisoformat(stamp), uuid.UUID(ident)
    except (ValueError, UnicodeError) as exc:
        raise AppError(
            "BAD_REQUEST", "That page marker is not valid.", status_code=422, field="cursor"
        ) from exc


def _filtered(
    access: Access,
    *,
    action: str | None,
    entity_type: str | None,
    entity_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
    since: datetime | None,
    until: datetime | None,
) -> Select[AuditEvent, str | None, str | None]:
    query = (
        select(AuditEvent, User.first_name, User.last_name)
        .outerjoin(User, User.id == AuditEvent.actor_user_id)
        .where(AuditEvent.company_id == access.company_id)
    )
    if action:
        query = query.where(AuditEvent.action.startswith(action, autoescape=True))
    if entity_type:
        query = query.where(AuditEvent.entity_type == entity_type)
    if entity_id:
        query = query.where(AuditEvent.entity_id == entity_id)
    if actor_user_id:
        query = query.where(AuditEvent.actor_user_id == actor_user_id)
    if since:
        query = query.where(AuditEvent.created_at >= since)
    if until:
        query = query.where(AuditEvent.created_at <= until)
    return query


def _out(event: AuditEvent, first: str | None, last: str | None) -> AuditEventOut:
    name = f"{first} {last}".strip() if first else None
    return AuditEventOut(
        id=event.id,
        created_at=event.created_at,
        action=event.action,
        actor_type=event.actor_type,  # type: ignore[arg-type]
        actor_user_id=event.actor_user_id,
        actor_name=name,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        summary=event.summary,
        before=event.before,
        after=event.after,
        reason=event.reason,
        ip=str(event.ip) if event.ip else None,
        user_agent=event.user_agent,
        request_id=event.request_id,
    )


@router.get("/audit-events", summary="Who did what, newest first")
async def list_audit_events(
    access: Annotated[Access, Depends(require("compliance.audit.read"))],
    action: Annotated[
        str | None, Query(max_length=100, description="Starts with, e.g. employee.")
    ] = None,
    entity_type: Annotated[str | None, Query(max_length=60)] = None,
    entity_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 50,
) -> AuditPage:
    query = _filtered(
        access,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        since=since,
        until=until,
    )
    if cursor:
        stamp, ident = _decode(cursor)
        query = query.where(tuple_(AuditEvent.created_at, AuditEvent.id) < (stamp, ident))
    result = await access.db.execute(
        query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(limit + 1)
    )
    rows = [(row[0], row[1], row[2]) for row in result.all()]
    page = rows[:limit]
    last_event = page[-1][0] if page else None
    return AuditPage(
        items=[_out(event, first, last) for event, first, last in page],
        next_cursor=(
            _encode(last_event.created_at, last_event.id)
            if last_event is not None and len(rows) > limit
            else None
        ),
    )


async def read_one_snapshot(db: AsyncSession) -> None:
    """Start a REPEATABLE READ transaction, so every page of an export reads the same snapshot
    (ISS-10). Nothing has been written yet when an export starts, so ending the request's first
    transaction loses nothing; the session's company and user are set again on the new one."""
    await db.commit()
    await db.connection(execution_options={"isolation_level": "REPEATABLE READ"})


def after_key(query: Any, event: AuditEvent) -> Any:
    """The next page of a newest-first query: strictly after ``event`` by (time, id)."""
    return query.where(tuple_(AuditEvent.created_at, AuditEvent.id) < (event.created_at, event.id))


def csv_cell(value: object) -> str:
    """A CSV cell that a spreadsheet will show as text, never run as a formula (OWASP)."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@router.get("/audit-events.csv", summary="The audit trail as a spreadsheet")
async def export_audit_events(
    access: Annotated[Access, Depends(require("compliance.audit.export"))],
    action: Annotated[str | None, Query(max_length=100)] = None,
    entity_type: Annotated[str | None, Query(max_length=60)] = None,
    entity_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> Response:
    base = _filtered(
        access,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        since=since,
        until=until,
    ).order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(
        ["Time (UTC)", "Who", "Action", "What", "Summary", "Reason", "IP address", "Request id"]
    )
    await read_one_snapshot(access.db)
    written, page = 0, base
    while written < EXPORT_LIMIT:
        size = min(_EXPORT_PAGE, EXPORT_LIMIT - written)
        result = await access.db.execute(page.limit(size))
        rows = [(row[0], row[1], row[2]) for row in result.all()]
        if not rows:
            break
        for event, first, last in rows:
            writer.writerow(
                [
                    csv_cell(event.created_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")),
                    csv_cell(f"{first} {last}".strip() if first else event.actor_type),
                    csv_cell(event.action),
                    csv_cell(f"{event.entity_type or ''} {event.entity_id or ''}".strip()),
                    csv_cell(event.summary),
                    csv_cell(event.reason),
                    csv_cell(event.ip),
                    csv_cell(event.request_id),
                ]
            )
            written += 1
        page = after_key(base, rows[-1][0])
    await access.audit(
        "audit.exported", entity_type="audit_events", summary=f"Exported {written} events"
    )
    await access.db.commit()
    return Response(
        out.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="audit-events.csv"',
            "Cache-Control": "no-store",
        },
    )
