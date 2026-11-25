"""The daily notification digest (plan 8.19, T14.2).

Each person who chose a daily e-mail gets one message a day that says how many notices are waiting.
Every notice is counted once: when a digest is sent, the notices in it are marked as digested, so
a second run the same day sends nothing new.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt
from app.db.session import TenantSession
from app.modules.companies.models import Company
from app.modules.email.models import EmailOutbox
from app.modules.email.outbox import PAYLOAD_CONTEXT
from app.modules.email.templates import check
from app.modules.identity.models import Membership, User
from app.modules.notifications.models import Notification, NotificationPreference

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

TEMPLATE = "notifications_digest"


async def send_digests(db: TenantSession, web_origin: str, now: datetime) -> int:
    # Only people whose membership of this company is active (ISS-08): a suspended member's
    # notices wait, and their other companies are unaffected.
    daily = (
        select(NotificationPreference.user_id)
        .join(
            Membership,
            (Membership.user_id == NotificationPreference.user_id)
            & (Membership.company_id == NotificationPreference.company_id),
        )
        .where(
            NotificationPreference.company_id == db.company_id,
            NotificationPreference.mode == "daily",
            Membership.status == "active",
        )
    )
    waiting = (
        await db.execute(
            select(Notification.user_id, func.count())
            .where(
                Notification.company_id == db.company_id,
                Notification.digested_at.is_(None),
                Notification.created_at <= now,
                Notification.user_id.in_(daily),
            )
            .group_by(Notification.user_id)
        )
    ).all()
    sent = 0
    for user_id, count in waiting:
        person = (
            await db.execute(
                select(User.first_name, User.email).where(
                    User.id == user_id,
                    User.is_active.is_(True),
                    User.email_verified_at.is_not(None),
                )
            )
        ).first()
        if person is None:  # no verified address to send to; the notices wait for the next digest
            continue
        first, email = person
        data = {
            "first_name": " ".join(first.split()) or "there",
            "count": str(count),
            "link": f"{web_origin}/dashboard",
        }
        check(TEMPLATE, data)
        db.add(
            EmailOutbox(
                to_address=email,
                template=TEMPLATE,
                payload=encrypt(json.dumps(data), context=PAYLOAD_CONTEXT),
            )
        )
        await db.execute(
            update(Notification)
            .where(
                Notification.company_id == db.company_id,
                Notification.user_id == user_id,
                Notification.digested_at.is_(None),
                Notification.created_at <= now,
            )
            .values(digested_at=now)
        )
        sent += 1
    return sent


async def reconcile_digests(
    owner: AsyncEngine, web_origin: str, *, now: datetime | None = None
) -> int:
    moment = now or datetime.now(UTC)
    async with AsyncSession(owner, expire_on_commit=False) as global_db:
        companies = (
            (await global_db.execute(select(Company.id).where(Company.status == "active")))
            .scalars()
            .all()
        )
    handled = 0
    for company_id in companies:
        async with TenantSession(owner, company_id=company_id) as db:
            handled += await send_digests(db, web_origin, moment)
            await db.commit()
    return handled


async def notifications_digest_daily(ctx: dict[str, Any]) -> int:
    owner, settings = ctx.get("owner_engine"), ctx.get("settings")
    if owner is None or settings is None:
        return 0
    return await reconcile_digests(owner, settings.web_origin, now=ctx.get("now"))
