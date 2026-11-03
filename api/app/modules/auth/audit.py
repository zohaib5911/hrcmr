"""Authentication events: tenant-scoped when known, otherwise private global events."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import insert

from app.db.ids import uuid7
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import AuditContext, record

if TYPE_CHECKING:
    import uuid

    from app.db.session import GlobalSession


async def security_event(
    db: GlobalSession,
    action: str,
    *,
    user_id: uuid.UUID | None = None,
    company_id: uuid.UUID | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
) -> None:
    if user_id is not None:
        await db.act_as(user_id)
    if company_id is not None:
        await db.company_for_this_transaction(company_id)
    if company_id is None:
        # INSERT RETURNING would need SELECT on private global rows. Keep these write-only.
        await db.execute(
            insert(AuditEvent)
            .inline()
            .values(
                id=uuid7(),
                company_id=None,
                actor_user_id=user_id,
                actor_type="user",
                action=action,
                entity_type="user",
                entity_id=user_id,
                ip=ip,
                user_agent=(user_agent or "")[:400] or None,
                request_id=request_id,
            )
        )
        return
    await record(
        db,
        AuditContext(
            company_id=company_id,
            actor_user_id=user_id,
            ip=ip,
            user_agent=user_agent,
            request_id=request_id,
        ),
        action,
        entity_type="user",
        entity_id=user_id,
    )
