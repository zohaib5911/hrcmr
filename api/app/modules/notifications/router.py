"""Own compliance messages and a live, permission-gated company attention feed (T7.6)."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.errors import NotFoundError
from app.core.rbac_matrix import scope_for
from app.core.schemas import RequestModel
from app.db.ids import uuid7
from app.modules.audit.router import _decode, _encode
from app.modules.compliance.hub_router import overview
from app.modules.notifications.models import Notification, NotificationPreference
from app.modules.notifications.schemas import (
    NotificationOut,
    NotificationPage,
    NotificationReadIn,
    NotificationsReadOut,
)
from app.modules.rbac.deps import Access, require

if TYPE_CHECKING:
    from sqlalchemy import Select

router = APIRouter(tags=["notifications"])
Own = Annotated[Access, Depends(require("company.overview.read"))]


def _may_read_compliance(access: Access) -> bool:
    return scope_for(access.role, "compliance.overview.read") is not None


# Notices about the person themselves: everyone sees these, whatever their role.
PERSONAL_KINDS = (
    "compliance.reminder_received",
    "leave.decision",
    "learning.overdue",
    "policy.assigned",
    "policy.reminder",
    "policy.overdue",
    "rota.published",
)


def _kinds(access: Access) -> tuple[str, ...]:
    kinds: tuple[str, ...] = PERSONAL_KINDS
    if scope_for(access.role, "recruitment.application.read") is not None:
        kinds += ("recruitment.application_received",)
    if _may_read_compliance(access):
        kinds += ("compliance.reminders_due",)
    if scope_for(access.role, "leave.request.approve") is not None:
        kinds += ("leave.request_created",)
    return kinds


def _query(access: Access) -> Select[Notification]:
    return select(Notification).where(
        Notification.user_id == access.caller.user_id,
        Notification.company_id == access.company_id,
        Notification.kind.in_(_kinds(access)),
    )


def _out(row: Notification) -> NotificationOut:
    return NotificationOut(
        id=row.id,
        kind=row.kind,
        title=row.title,
        body=row.body,
        link=row.link,
        read_at=row.read_at,
        created_at=row.created_at,
    )


@router.get("/notifications", response_model=NotificationPage)
async def notifications(
    access: Own,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> NotificationPage:
    query = _query(access)
    unread = (
        await access.db.execute(
            select(func.count()).select_from(query.where(Notification.read_at.is_(None)).subquery())
        )
    ).scalar_one()
    if cursor:
        stamp, ident = _decode(cursor)
        query = query.where(tuple_(Notification.created_at, Notification.id) < (stamp, ident))
    rows = list(
        (
            await access.db.execute(
                query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(
                    limit + 1
                )
            )
        ).scalars()
    )
    page = rows[:limit]
    attention = (await overview(access)).attention if _may_read_compliance(access) else []
    last = page[-1] if page else None
    return NotificationPage(
        items=[_out(row) for row in page],
        next_cursor=_encode(last.created_at, last.id) if last and len(rows) > limit else None,
        unread=unread,
        needs_attention=attention[:5],
        attention_count=len(attention),
    )


@router.post("/notifications/read-all", response_model=NotificationsReadOut)
async def read_all(access: Own) -> NotificationsReadOut:
    ids = _query(access).with_only_columns(Notification.id).where(Notification.read_at.is_(None))
    marked = list(
        (
            await access.db.execute(
                update(Notification)
                .where(Notification.id.in_(ids))
                .values(read_at=datetime.now(UTC), updated_by=access.caller.user_id)
                .returning(Notification.id)
            )
        ).scalars()
    )
    if marked:
        await access.audit(
            "notification.read_all", entity_type="notification", after={"marked": len(marked)}
        )
    await access.db.commit()
    return NotificationsReadOut(marked=len(marked))


@router.patch("/notifications/{notification_id}", response_model=NotificationOut)
async def read_notification(
    notification_id: uuid.UUID, body: NotificationReadIn, access: Own
) -> NotificationOut:
    row = (
        await access.db.execute(
            _query(access).where(Notification.id == notification_id).with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        await access.audit("notification.read", entity_type="notification", entity_id=row.id)
        await access.db.commit()
    return _out(row)


class PreferenceIn(RequestModel):
    mode: Literal["immediate", "daily", "off"]


class PreferenceOut(BaseModel):
    mode: str  # one of the three EMAIL_MODES; the database check enforces it


@router.get("/me/notification-preferences", response_model=PreferenceOut)
async def get_preferences(access: Own) -> PreferenceOut:
    mode = (
        await access.db.execute(
            select(NotificationPreference.mode).where(
                NotificationPreference.company_id == access.company_id,
                NotificationPreference.user_id == access.caller.user_id,
            )
        )
    ).scalar_one_or_none()
    return PreferenceOut(mode=mode or "immediate")


@router.put("/me/notification-preferences", response_model=PreferenceOut)
async def set_preferences(body: PreferenceIn, access: Own) -> PreferenceOut:
    statement = (
        pg_insert(NotificationPreference)
        .values(
            id=uuid7(),
            company_id=access.company_id,
            user_id=access.caller.user_id,
            mode=body.mode,
        )
        .on_conflict_do_update(
            constraint="uq_notification_preferences_company_user",
            set_={"mode": body.mode, "updated_by": access.caller.user_id},
        )
    )
    await access.db.execute(statement)
    await access.audit(
        "notification.preferences_changed", entity_type="notification", after={"mode": body.mode}
    )
    await access.db.commit()
    return PreferenceOut(mode=body.mode)
