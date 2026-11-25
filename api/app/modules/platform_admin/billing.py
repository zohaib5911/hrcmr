"""Subscriptions for the platform admins (T17.4, plan 8.16).

The list reads the database only: the Stripe ids are shown so that a lookup in Stripe's own
dashboard is one click away, and no Stripe call is made per row.

There is no refund action, for customers or for the platform (owner decision, 2026-11-25: payments
are never refunded). A payment the provider reverses (a refund made in Stripe itself, or a lost
dispute) is still reconciled by the webhook in billing/service.py and shows here as refunded.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, func, select

from app.modules.billing.models import Subscription
from app.modules.companies.models import Company
from app.modules.platform_admin.schemas import SubscriptionRow, SubscriptionsOut

if TYPE_CHECKING:
    from app.db.session import GlobalSession

PAGE_MAX = 100


def _row(subscription: Subscription, company_name: str) -> SubscriptionRow:
    return SubscriptionRow(
        id=subscription.id,
        company_id=subscription.company_id,
        company_name=company_name,
        plan=subscription.plan,
        status=subscription.status,
        created_at=subscription.created_at,
        current_period_end=subscription.current_period_end,
        cancel_at=subscription.cancel_at,
        refunded_at=subscription.refunded_at,
        stripe_subscription_id=subscription.stripe_subscription_id,
        stripe_payment_intent_id=subscription.stripe_payment_intent_id,
    )


async def subscriptions(
    db: GlobalSession,
    *,
    plan: str | None,
    refunded: bool | None,
    limit: int,
    offset: int,
) -> SubscriptionsOut:
    filters: list[Any] = []
    if plan:
        filters.append(Subscription.plan == plan)
    if refunded is True:
        filters.append(Subscription.refunded_at.is_not(None))
    elif refunded is False:
        filters.append(Subscription.refunded_at.is_(None))
    query = select(Subscription, Company.name).join(Company, Company.id == Subscription.company_id)
    count = select(func.count(Subscription.id))
    if filters:
        query = query.where(and_(*filters))
        count = count.where(and_(*filters))
    total = await db.scalar(count)
    rows = await db.execute(
        query.order_by(Subscription.created_at.desc(), Subscription.id).limit(limit).offset(offset)
    )
    items = [_row(subscription, name) for subscription, name in rows.all()]
    return SubscriptionsOut(items=items, total=int(total or 0))
