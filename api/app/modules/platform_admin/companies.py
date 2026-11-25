"""Companies for the platform admins (T17.2): search, detail, and the four audited actions.

A company's state is a column, so the actions only change that column, and tenant requests already
refuse a company whose status is not active (``ACCOUNT_SUSPENDED``, rbac/deps.py). Nothing is erased
here: marking a company for deletion sets its status and blocks access; the purge still runs only
from the company's own confirmed deletion request (T16.5).
"""

from __future__ import annotations

import uuid  # noqa: TC003  (SQLAlchemy and pydantic read the types at runtime)
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select

from app.core.errors import AppError, NotFoundError
from app.db.session import GlobalSession  # noqa: TC001
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import AuditContext, record
from app.modules.companies.models import Company
from app.modules.identity.models import Membership, User
from app.modules.platform_admin.schemas import (
    CompaniesOut,
    CompanyDetailOut,
    CompanyRow,
    MemberOut,
    PlatformEventOut,
)

PAGE_MAX = 100
EVENTS_SHOWN = 20
COMPANY_ACTIONS = (
    "platform.company_suspended",
    "platform.company_reactivated",
    "platform.company_plan_extended",
    "platform.company_comp_granted",
    "platform.company_marked_for_deletion",
    "platform.support_started",
    "platform.support_writes_changed",
    "platform.support_ended",
)


def like(text: str) -> str:
    """A substring pattern for ILIKE, with the wildcard characters taken as plain text."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _members_count() -> Any:
    return (
        select(func.count(Membership.id))
        .where(Membership.company_id == Company.id)
        .correlate(Company)
        .scalar_subquery()
    )


def _last_active() -> Any:
    return (
        select(func.max(User.last_login_at))
        .select_from(Membership)
        .join(User, User.id == Membership.user_id)
        .where(Membership.company_id == Company.id)
        .correlate(Company)
        .scalar_subquery()
    )


async def search(
    db: GlobalSession,
    *,
    q: str | None,
    plan: str | None,
    status: str | None,
    created_since: datetime | None,
    active_since: datetime | None,
    limit: int,
    offset: int,
) -> CompaniesOut:
    last_active = _last_active()
    filters: list[Any] = []
    if q:
        pattern = like(q.strip())
        filters.append(
            or_(
                Company.name.ilike(pattern),
                Company.slug.ilike(pattern),
                Company.contact_email.ilike(pattern),
            )
        )
    if plan:
        filters.append(Company.plan == plan)
    if status:
        filters.append(Company.status == status)
    if created_since is not None:
        filters.append(Company.created_at >= created_since)
    if active_since is not None:
        filters.append(last_active >= active_since)

    count = select(func.count(Company.id))
    query = select(Company, _members_count().label("members"), last_active.label("last_active_at"))
    if filters:
        count = count.where(and_(*filters))
        query = query.where(and_(*filters))
    total = await db.scalar(count)
    rows = await db.execute(
        query.order_by(Company.created_at.desc(), Company.id).limit(limit).offset(offset)
    )
    items = [_row(company, members, seen) for company, members, seen in rows.all()]
    return CompaniesOut(items=items, total=int(total or 0))


def _row(company: Company, members: int, last_active_at: datetime | None) -> CompanyRow:
    return CompanyRow(
        id=company.id,
        name=company.name,
        slug=company.slug,
        contact_email=company.contact_email,
        status=company.status,
        plan=company.plan,
        subscription_status=company.subscription_status,
        subscription_ends_at=company.subscription_ends_at,
        created_at=company.created_at,
        last_active_at=last_active_at,
        members=int(members or 0),
    )


async def company_or_404(
    db: GlobalSession, company_id: uuid.UUID, *, lock: bool = False
) -> Company:
    company = await db.get(Company, company_id, with_for_update=lock, populate_existing=lock)
    if company is None:
        raise NotFoundError("We could not find that company.")
    return company


async def detail(db: GlobalSession, company: Company) -> CompanyDetailOut:
    counts = await db.execute(
        select(func.count(Membership.id), func.max(User.last_login_at))
        .select_from(Membership)
        .join(User, User.id == Membership.user_id)
        .where(Membership.company_id == company.id)
    )
    members, last_active = counts.one()
    people = await db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.company_id == company.id)
        .order_by(User.last_name, User.first_name, User.email)
    )
    events = await db.execute(
        select(AuditEvent)
        .where(
            AuditEvent.company_id.is_(None),
            AuditEvent.entity_type == "company",
            AuditEvent.entity_id == company.id,
            AuditEvent.action.in_(COMPANY_ACTIONS),
        )
        .order_by(AuditEvent.created_at.desc())
        .limit(EVENTS_SHOWN)
    )
    base = _row(company, int(members or 0), last_active)
    return CompanyDetailOut(
        **base.model_dump(),
        trading_name=company.trading_name,
        registered_number=company.registered_number,
        subscription_started_at=company.subscription_started_at,
        payment_grace_ends_at=company.payment_grace_ends_at,
        stripe_customer_id=company.stripe_customer_id,
        stripe_subscription_id=company.stripe_subscription_id,
        people=[
            MemberOut(
                user_id=user.id,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                role=membership.role,
                status=membership.status,
                locked=not user.is_active,
                mfa_enabled=user.mfa_enabled,
                last_login_at=user.last_login_at,
            )
            for membership, user in people.all()
        ],
        events=[
            PlatformEventOut(
                action=event.action,
                reason=event.reason,
                summary=event.summary,
                created_at=event.created_at,
            )
            for event in events.scalars().all()
        ],
    )


async def suspend(db: GlobalSession, context: AuditContext, company: Company, reason: str) -> None:
    if company.status != "active":
        raise AppError("NOT_ACTIVE", "Only an active company can be suspended.", status_code=409)
    before = {"status": company.status}
    company.status = "suspended"
    await record(
        db,
        context,
        "platform.company_suspended",
        entity_type="company",
        entity_id=company.id,
        before=before,
        after={"status": company.status},
        reason=reason,
    )


async def reactivate(
    db: GlobalSession, context: AuditContext, company: Company, reason: str
) -> None:
    if company.status != "suspended":
        raise AppError(
            "NOT_SUSPENDED", "Only a suspended company can be reactivated.", status_code=409
        )
    before = {"status": company.status}
    company.status = "active"
    await record(
        db,
        context,
        "platform.company_reactivated",
        entity_type="company",
        entity_id=company.id,
        before=before,
        after={"status": company.status},
        reason=reason,
    )


async def extend_plan(
    db: GlobalSession,
    context: AuditContext,
    company: Company,
    *,
    days: int,
    reason: str,
    now: datetime,
) -> None:
    """Give extra days of access for free (a comp, plan 8.16).

    An active 10-year plan: its end date is the access date, so the date moves (as built in T17.2).
    Any other company (annual, free, or a lapsed plan): a complimentary end date (``comp_until``)
    moves, separate from Stripe, so no Stripe record is changed and billing history stays true
    (owner answer 5, 2026-11-08). Both are audited with the reason."""
    if company.status in ("pending_deletion", "deleted"):
        raise AppError(
            "COMPANY_CLOSED", "This company is closing; it cannot be extended.", status_code=409
        )
    if company.plan == "ten_year" and company.subscription_status == "active":
        old_end = company.subscription_ends_at
        start = old_end if old_end is not None and old_end > now else now
        new_end = start + timedelta(days=days)
        company.subscription_ends_at = new_end
        await record(
            db,
            context,
            "platform.company_plan_extended",
            entity_type="company",
            entity_id=company.id,
            before={"subscription_ends_at": old_end.isoformat() if old_end else None},
            after={"subscription_ends_at": new_end.isoformat()},
            reason=reason,
            summary=f"Extended by {days} days",
        )
        return
    old_comp = company.comp_until
    start = old_comp if old_comp is not None and old_comp > now else now
    new_comp = start + timedelta(days=days)
    company.comp_until = new_comp
    await record(
        db,
        context,
        "platform.company_comp_granted",
        entity_type="company",
        entity_id=company.id,
        before={"comp_until": old_comp.isoformat() if old_comp else None},
        after={"comp_until": new_comp.isoformat()},
        reason=reason,
        summary=f"Complimentary access extended by {days} days",
    )


async def mark_for_deletion(
    db: GlobalSession, context: AuditContext, company: Company, reason: str
) -> None:
    if company.status not in ("active", "suspended"):
        raise AppError(
            "NOT_MARKABLE",
            "Only an active or suspended company can be marked for deletion.",
            status_code=409,
        )
    before = {"status": company.status}
    company.status = "pending_deletion"
    await record(
        db,
        context,
        "platform.company_marked_for_deletion",
        entity_type="company",
        entity_id=company.id,
        before=before,
        after={"status": company.status},
        reason=reason,
    )
