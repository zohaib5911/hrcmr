"""The account deletion executor (T16.5, plan 8.16): every hour, delete the companies that are due.

For each confirmed request whose 7 days have passed (and that nobody withdrew):

1. stop billing: a live annual subscription is ended in Stripe (no deletion while it still bills);
2. delete every stored object of the company (its files, reports and exports);
3. in one transaction: delete every tenant row, delete the people who belonged to no other company,
   empty the company row down to a stub (id, status ``deleted``, payment ids), replace the audit
   trail with one ``company.deleted`` event, mark the request done and queue the final e-mail.

A failure leaves the request due, so the next hour tries again; every step can run twice.
"""

from __future__ import annotations

import json
import uuid  # noqa: TC003
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt
from app.core.logging import get_logger
from app.db.purge import delete_company_rows
from app.integrations.stripe import Stripe
from app.modules.audit.service import AuditContext, record
from app.modules.billing.service import ENDED
from app.modules.companies.models import Company
from app.modules.deletion.models import DeletionRequest
from app.modules.email.models import EmailOutbox
from app.modules.email.outbox import PAYLOAD_CONTEXT
from app.modules.email.templates import check
from app.modules.files.models import File
from app.modules.identity.models import Membership, PlatformAdmin, User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from app.integrations.storage import Storage

logger = get_logger("app.deletion")

BATCH = 20
KEY_PREFIX = "company/{company_id}/"
# Company columns emptied in the stub. Kept: id, status, plan and subscription fields, Stripe ids
# (for the payment records), and settings with no personal data.
SCRUBBED = (
    "trading_name",
    "registered_number",
    "type_of_organisation",
    "trading_period",
    "sector",
    "size_band",
    "contact_email",
    "contact_phone",
    "website",
    "logo_file_id",
    "previous_company_name",
    "penalty_illegal_working_status",
    "setup_checklist_dismissed_at",
)


def due(now: datetime) -> Any:
    return select(DeletionRequest.company_id, DeletionRequest.id).where(
        DeletionRequest.confirmed_at.is_not(None),
        DeletionRequest.withdrawn_at.is_(None),
        DeletionRequest.completed_at.is_(None),
        DeletionRequest.scheduled_for <= now,
    )


async def _stop_billing(stripe: Stripe, company: Company) -> None:
    subscription_id = company.stripe_subscription_id
    if company.plan != "annual" or not subscription_id or company.subscription_status in ENDED:
        return
    live = await stripe.retrieve_subscription(subscription_id)
    if live.get("status") not in ENDED:
        await stripe.cancel_now(subscription_id)
    company.subscription_status = "canceled"


async def _delete_objects(storage: Storage | None, keys: list[str], company_id: uuid.UUID) -> int:
    prefix = KEY_PREFIX.format(company_id=company_id)
    if storage is None:
        if keys:
            raise RuntimeError("file storage is not configured")
        return 0
    found = {item.key for item in await storage.list_objects(prefix)}
    for key in sorted(found | set(keys)):
        await storage.delete(key)
    return len(found | set(keys))


async def _people(db: AsyncSession, company_id: uuid.UUID) -> tuple[list[User], list[uuid.UUID]]:
    """The company's active admins (for the final e-mail), and every member who belongs to no
    other company and is not one of our own staff (their user account goes too)."""
    members = (
        await db.execute(
            select(User, Membership.role, Membership.status)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.company_id == company_id)
            .order_by(User.id)
        )
    ).all()
    admins = [
        user
        for user, role, status in members
        if role == "company_admin" and status == "active" and user.is_active
    ]
    elsewhere = exists().where(Membership.user_id == User.id, Membership.company_id != company_id)
    staff = exists().where(PlatformAdmin.user_id == User.id)
    alone = (
        await db.execute(
            select(User.id).where(
                User.id.in_([user.id for user, _, _ in members]), ~elsewhere, ~staff
            )
        )
    ).scalars()
    return admins, list(alone)


async def _delete_users(db: AsyncSession, user_ids: list[uuid.UUID]) -> tuple[int, int]:
    """Deletes each user; one still referenced elsewhere is emptied instead. (deleted, emptied)"""
    deleted = emptied = 0
    for user_id in user_ids:
        try:
            async with db.begin_nested():
                await db.execute(delete(User).where(User.id == user_id))
            deleted += 1
        except IntegrityError:
            user = await db.get(User, user_id)
            if user is None:
                continue
            user.email = f"deleted-{user_id}@deleted.invalid"
            user.first_name, user.last_name = "Deleted", "user"
            user.password_hash, user.mfa_secret, user.recovery_codes_hash = None, None, []
            user.mfa_enabled, user.is_active = False, False
            emptied += 1
    return deleted, emptied


def _final_email(db: AsyncSession, email: str, first_name: str, company: str, when: str) -> None:
    data = {"first_name": first_name, "company_name": company, "deletion_date": when}
    check("account_deleted", data)
    db.add(
        EmailOutbox(
            to_address=email,
            template="account_deleted",
            payload=encrypt(json.dumps(data), context=PAYLOAD_CONTEXT),
        )
    )


async def purge_company(
    owner: AsyncEngine,
    storage: Storage | None,
    stripe: Stripe,
    company_id: uuid.UUID,
    request_id: uuid.UUID,
    *,
    now: datetime,
) -> bool:
    """Deletes one company if its request is still due. True when it was deleted now."""
    async with AsyncSession(owner, expire_on_commit=False) as db:
        request = (
            await db.execute(
                select(DeletionRequest)
                .where(DeletionRequest.id == request_id, DeletionRequest.company_id == company_id)
                .with_for_update(skip_locked=True)
            )
        ).scalar_one_or_none()
        if request is None or request.completed_at is not None or request.withdrawn_at is not None:
            return False
        if request.scheduled_for is None or request.scheduled_for > now:
            return False
        company = await db.get(Company, company_id, with_for_update=True)
        if company is None:
            return False

        if request.started_at is None:
            # Commit the irreversible phase BEFORE removing any external object. A failed purge
            # stays frozen and retryable; it can no longer masquerade as a withdrawable request.
            request.started_at = now
            company.status = "pending_deletion"
            await db.commit()
            # Reacquire both locks after the commit. Another worker may have finished meanwhile.
            request = (
                await db.execute(
                    select(DeletionRequest)
                    .where(DeletionRequest.id == request_id)
                    .with_for_update(skip_locked=True)
                    .execution_options(populate_existing=True)
                )
            ).scalar_one_or_none()
            if request is None or request.completed_at is not None:
                return False
            company = await db.get(
                Company, company_id, with_for_update=True, populate_existing=True
            )
            if company is None:
                return False
        await _stop_billing(stripe, company)
        keys = list(
            (await db.execute(select(File.storage_key).where(File.company_id == company_id)))
            .scalars()
            .all()
        )
        objects = await _delete_objects(storage, keys, company_id)

        admins, alone = await _people(db, company_id)
        company_name = company.name
        recipients = [(user.email, user.first_name) for user in admins]
        counts = await delete_company_rows(db, company_id)
        users_deleted, users_emptied = await _delete_users(db, alone)

        for name in SCRUBBED:
            setattr(company, name, None)
        company.name = "Deleted company"
        company.slug = f"deleted-{company.id}"
        company.status = "deleted"
        company.ai_features_enabled = False
        request.completed_at = now
        request.code_hash = None
        await record(
            db,
            AuditContext(company_id=company_id, actor_user_id=None, actor_type="system"),
            "company.deleted",
            entity_type="company",
            entity_id=company_id,
            after={"deleted_at": now.isoformat()},
        )
        when = f"{now:%-d %B %Y}"
        for email, first_name in recipients:
            _final_email(db, email, first_name, company_name, when)
        await db.commit()
    logger.info(
        "company_deleted",
        company_id=str(company_id),
        tables=len(counts),
        rows=sum(counts.values()),
        objects=objects,
        users_deleted=users_deleted,
        users_emptied=users_emptied,
    )
    return True


async def deletion_executor_hourly(ctx: dict[str, Any]) -> int:
    owner: AsyncEngine | None = ctx.get("owner_engine")
    if owner is None:
        return 0
    now = ctx.get("now") or datetime.now(UTC)
    stripe: Stripe = ctx.get("stripe") or Stripe.from_settings(ctx["settings"])
    async with AsyncSession(owner) as db:
        waiting = (
            await db.execute(due(now).order_by(DeletionRequest.scheduled_for).limit(BATCH))
        ).all()
    done = 0
    for company_id, request_id in waiting:
        try:
            done += await purge_company(
                owner, ctx.get("storage"), stripe, company_id, request_id, now=now
            )
        except Exception as exc:
            # Stays due: the next hour tries again. Nothing about the company's data is logged.
            logger.warning(
                "company_deletion_failed", company_id=str(company_id), kind=type(exc).__name__
            )
    return done
