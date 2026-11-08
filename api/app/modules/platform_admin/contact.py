"""The contact inbox for the platform admins (T17.4, plan 6.12 and 8.18).

Messages come from the public contact form (T18.1). This reads them and marks them handled or open
again. A change is audited under the platform admin, with the handled state before and after; a
mark that changes nothing is not audited. A message holds personal data, so only platform admins
reach it: no tenant route reads the table.
"""

from __future__ import annotations

import uuid  # noqa: TC003  (SQLAlchemy and pydantic read the types at runtime)
from datetime import datetime  # noqa: TC003  (same)
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.core.errors import NotFoundError
from app.modules.audit.service import AuditContext, record
from app.modules.contact.models import ContactMessage
from app.modules.platform_admin.schemas import ContactMessageRow, ContactMessagesOut

if TYPE_CHECKING:
    from app.db.session import GlobalSession

PAGE_MAX = 100


def row(message: ContactMessage) -> ContactMessageRow:
    return ContactMessageRow(
        id=message.id,
        name=message.name,
        company=message.company,
        email=message.email,
        topic=message.topic,
        message=message.message,
        created_at=message.created_at,
        handled_at=message.handled_at,
    )


async def messages(
    db: GlobalSession, *, handled: bool | None, limit: int, offset: int
) -> ContactMessagesOut:
    filters: list[Any] = []
    if handled is True:
        filters.append(ContactMessage.handled_at.is_not(None))
    elif handled is False:
        filters.append(ContactMessage.handled_at.is_(None))
    query = select(ContactMessage)
    count = select(func.count(ContactMessage.id))
    if filters:
        query = query.where(*filters)
        count = count.where(*filters)
    total = await db.scalar(count)
    found = await db.execute(
        query.order_by(ContactMessage.created_at.desc(), ContactMessage.id)
        .limit(limit)
        .offset(offset)
    )
    items = [row(message) for message in found.scalars().all()]
    return ContactMessagesOut(items=items, total=int(total or 0))


async def message_or_404(db: GlobalSession, message_id: uuid.UUID) -> ContactMessage:
    message = await db.get(ContactMessage, message_id)
    if message is None:
        raise NotFoundError("We could not find that message.")
    return message


async def set_handled(
    db: GlobalSession,
    context: AuditContext,
    message: ContactMessage,
    *,
    handled: bool,
    now: datetime,
) -> None:
    if (message.handled_at is not None) == handled:
        return  # already in that state: nothing changes and nothing is audited
    before = {"handled": message.handled_at is not None}
    message.handled_at = now if handled else None
    await record(
        db,
        context,
        "platform.contact_updated",
        entity_type="contact_message",
        entity_id=message.id,
        before=before,
        after={"handled": handled},
        summary="Marked handled" if handled else "Marked open again",
    )
