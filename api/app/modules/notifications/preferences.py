"""How each person wants e-mail about their notices: now, in a daily digest, or off."""

from __future__ import annotations

import uuid  # noqa: TC003
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.notifications.models import NotificationPreference

if TYPE_CHECKING:
    from app.db.session import TenantSession


async def email_modes(db: TenantSession, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """The saved mode for each person who has one. Anyone not listed is on "immediate"."""
    if not user_ids:
        return {}
    rows = (
        await db.execute(
            select(NotificationPreference.user_id, NotificationPreference.mode).where(
                NotificationPreference.company_id == db.company_id,
                NotificationPreference.user_id.in_(user_ids),
            )
        )
    ).all()
    return dict(rows)
