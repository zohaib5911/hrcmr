"""The platform audit log for the platform admins (T17.6, plan 8.18): the company-less trail, with
filters, and a CSV export. The export is itself recorded. Tenant events are not in this log."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.modules.audit.models import AuditEvent
from app.modules.audit.router import EXPORT_LIMIT, csv_cell
from app.modules.audit.service import AuditContext, record
from app.modules.identity.models import User
from app.modules.platform_admin.schemas import AuditLogOut, AuditLogRow

if TYPE_CHECKING:
    from app.db.session import GlobalSession

PAGE_MAX = 200
EXPORT_PAGE = 1000


def _escape(text: str) -> str:
    """``text`` with the LIKE wildcards taken as plain characters."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _filtered(
    *,
    action: str | None,
    entity_type: str | None,
    actor_type: str | None,
    since: datetime | None,
    until: datetime | None,
) -> list[Any]:
    filters: list[Any] = []
    if action:
        # A trailing dot matches a whole family of actions, e.g. "platform." or "job.".
        filters.append(
            AuditEvent.action.like(_escape(action) + "%")
            if action.endswith(".")
            else AuditEvent.action == action
        )
    if entity_type:
        filters.append(AuditEvent.entity_type == entity_type)
    if actor_type:
        filters.append(AuditEvent.actor_type == actor_type)
    if since is not None:
        filters.append(AuditEvent.created_at >= since)
    if until is not None:
        filters.append(AuditEvent.created_at < until)
    return filters


def _query(filters: list[Any]) -> Any:
    query = select(AuditEvent, User.email).outerjoin(User, User.id == AuditEvent.actor_user_id)
    return query.where(*filters) if filters else query


async def events(
    db: GlobalSession,
    *,
    action: str | None,
    entity_type: str | None,
    actor_type: str | None,
    since: datetime | None,
    until: datetime | None,
    limit: int,
    offset: int,
) -> AuditLogOut:
    filters = _filtered(
        action=action, entity_type=entity_type, actor_type=actor_type, since=since, until=until
    )
    total = await db.scalar(select(func.count(AuditEvent.id)).where(*filters))
    found = await db.execute(
        _query(filters)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(limit)
        .offset(offset)
    )
    items = [_row(event, email) for event, email in found.all()]
    return AuditLogOut(items=items, total=int(total or 0))


def _row(event: AuditEvent, email: str | None) -> AuditLogRow:
    return AuditLogRow(
        id=event.id,
        created_at=event.created_at,
        actor_type=event.actor_type,
        actor=email or event.actor_type,
        action=event.action,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        summary=event.summary,
        reason=event.reason,
        request_id=event.request_id,
    )


async def export_csv(
    db: GlobalSession,
    context: AuditContext,
    *,
    action: str | None,
    entity_type: str | None,
    actor_type: str | None,
    since: datetime | None,
    until: datetime | None,
) -> bytes:
    filters = _filtered(
        action=action, entity_type=entity_type, actor_type=actor_type, since=since, until=until
    )
    base = _query(filters).order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(
        ["Time (UTC)", "Who", "Action", "What", "Summary", "Reason", "IP address", "Request id"]
    )
    written, offset = 0, 0
    while written < EXPORT_LIMIT:
        rows = (await db.execute(base.limit(EXPORT_PAGE).offset(offset))).all()
        if not rows:
            break
        for event, email in rows:
            writer.writerow(
                [
                    csv_cell(event.created_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")),
                    csv_cell(email or event.actor_type),
                    csv_cell(event.action),
                    csv_cell(f"{event.entity_type or ''} {event.entity_id or ''}".strip()),
                    csv_cell(event.summary),
                    csv_cell(event.reason),
                    csv_cell(event.ip),
                    csv_cell(event.request_id),
                ]
            )
            written += 1
        offset += EXPORT_PAGE
    await record(
        db,
        context,
        "platform.audit_exported",
        entity_type="audit_events",
        summary=f"Exported {written} platform events",
    )
    return out.getvalue().encode("utf-8-sig")
