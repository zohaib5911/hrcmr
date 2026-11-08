"""Announcement banners for the platform admins (T17.5, plan 8.18 Content).

A banner is scheduled for one region and a period. It is live from its start until its end, or
until a platform admin ends it early. Creating and ending are audited under the platform admin.
"""

from __future__ import annotations

import uuid  # noqa: TC003  (SQLAlchemy and pydantic read the types at runtime)
from datetime import datetime  # noqa: TC003  (same)
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.core.errors import AppError, NotFoundError
from app.modules.announcements.models import Announcement
from app.modules.audit.service import AuditContext, record
from app.modules.platform_admin.schemas import AnnouncementRow, AnnouncementsOut

if TYPE_CHECKING:
    from app.db.session import GlobalSession


def status_of(item: Announcement, now: datetime) -> str:
    if item.ended_at is not None or now >= item.ends_at:
        return "ended"
    if now < item.starts_at:
        return "scheduled"
    return "live"


def row(item: Announcement, now: datetime) -> AnnouncementRow:
    return AnnouncementRow(
        id=item.id,
        region=item.region,
        title=item.title,
        body=item.body,
        starts_at=item.starts_at,
        ends_at=item.ends_at,
        ended_at=item.ended_at,
        status=status_of(item, now),
    )


async def announcements(db: GlobalSession, now: datetime) -> AnnouncementsOut:
    found = (
        (await db.execute(select(Announcement).order_by(Announcement.starts_at.desc())))
        .scalars()
        .all()
    )
    items = [row(item, now) for item in found]
    return AnnouncementsOut(items=items, total=len(items))


async def create(
    db: GlobalSession,
    context: AuditContext,
    *,
    region: str,
    title: str,
    body: str,
    starts_at: datetime,
    ends_at: datetime,
    reason: str,
    now: datetime,
) -> Announcement:
    if starts_at.tzinfo is None or ends_at.tzinfo is None:
        raise AppError(
            "NEEDS_TIME_ZONE", "Give the start and end with a time zone.", status_code=422
        )
    if ends_at <= starts_at:
        raise AppError(
            "INVALID_PERIOD",
            "The banner must end after it starts.",
            status_code=422,
            field="ends_at",
        )
    if ends_at <= now:
        raise AppError(
            "ENDS_IN_PAST", "The banner must end in the future.", status_code=422, field="ends_at"
        )
    item = Announcement(
        region=region,
        title=title,
        body=body,
        starts_at=starts_at,
        ends_at=ends_at,
        created_by=context.actor_user_id,
    )
    db.add(item)
    await db.flush()
    await record(
        db,
        context,
        "platform.announcement_created",
        entity_type="announcement",
        entity_id=item.id,
        after={
            "region": region,
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
        },
        reason=reason,
        summary=f"Banner for {region} scheduled",
    )
    return item


async def end(
    db: GlobalSession,
    context: AuditContext,
    announcement_id: uuid.UUID,
    *,
    reason: str,
    now: datetime,
) -> Announcement:
    item = await db.get(Announcement, announcement_id)
    if item is None:
        raise NotFoundError("We could not find that banner.")
    if status_of(item, now) == "ended":
        raise AppError("ALREADY_ENDED", "This banner has already ended.", status_code=409)
    item.ended_at = now
    await record(
        db,
        context,
        "platform.announcement_ended",
        entity_type="announcement",
        entity_id=item.id,
        before={"status": status_of(item, now)},
        after={"status": "ended"},
        reason=reason,
        summary="Banner ended early",
    )
    return item
