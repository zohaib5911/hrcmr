"""Subscriptions and refunds for the platform admins (T17.4, plan 8.16).

The list reads the database only: the Stripe ids are shown so that a lookup in Stripe's own
dashboard is one click away, and no Stripe call is made per row.

A refund is one full refund of the latest payment behind a purchase: an annual plan's latest
invoice, or a 10-year payment. It goes through the T16 Stripe client with the same idempotency key
the self-serve refund uses (``refund-{payment_intent}``), so one payment is refunded at most once,
however the two paths race or a request is retried. The refund is recorded and audited here. The
plan itself changes when Stripe's ``charge.refunded`` event arrives, as it does for a refund made
in Stripe's dashboard (billing/service.py).
"""

from __future__ import annotations

import uuid  # noqa: TC003  (SQLAlchemy reads the types at runtime)
from datetime import datetime  # noqa: TC003  (same)
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, func, select

from app.core.errors import AppError, NotFoundError
from app.core.logging import get_logger
from app.integrations.stripe import StripeError
from app.modules.audit.service import AuditContext, record
from app.modules.billing.models import Subscription
from app.modules.billing.service import _first_payment_intent
from app.modules.companies.models import Company
from app.modules.platform_admin.schemas import SubscriptionRow, SubscriptionsOut

if TYPE_CHECKING:
    from app.db.session import GlobalSession
    from app.integrations.stripe import Stripe

logger = get_logger("app.platform_admin")
PAGE_MAX = 100
UNAVAILABLE = "We could not reach our payment provider. Try again in a few minutes."


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


async def subscription_or_404(db: GlobalSession, subscription_id: uuid.UUID) -> Subscription:
    subscription = await db.get(Subscription, subscription_id)
    if subscription is None:
        raise NotFoundError("We could not find that purchase.")
    return subscription


async def row_for(db: GlobalSession, subscription: Subscription) -> SubscriptionRow:
    name = await db.scalar(select(Company.name).where(Company.id == subscription.company_id))
    return _row(subscription, name or "")


async def _payment_to_refund(stripe: Stripe, subscription: Subscription) -> str | None:
    if subscription.plan == "annual":
        if subscription.stripe_subscription_id is None:
            return None
        return await _first_payment_intent(stripe, subscription.stripe_subscription_id)
    return subscription.stripe_payment_intent_id


async def refund(
    db: GlobalSession,
    stripe: Stripe,
    context: AuditContext,
    subscription: Subscription,
    *,
    reason: str,
    now: datetime,
) -> str:
    """Refund the latest payment behind ``subscription`` in full. Returns Stripe's refund id.

    Nothing is committed here: the caller commits once the refund is recorded. If that commit
    fails after Stripe refunded, a retry sends the same idempotency key and Stripe answers with the
    first refund, so the payment is still refunded once."""
    if subscription.refunded_at is not None:
        raise AppError(
            "ALREADY_REFUNDED", "This payment has already been refunded.", status_code=409
        )
    if not stripe.enabled:
        raise AppError("PAYMENTS_NOT_SET_UP", "Payments are not set up yet.", status_code=503)
    try:
        payment_intent = await _payment_to_refund(stripe, subscription)
        if payment_intent is None:
            raise AppError(
                "NOTHING_TO_REFUND",
                "There is no payment to refund on this purchase.",
                status_code=409,
            )
        answer = await stripe.create_refund(
            payment_intent=payment_intent, idempotency_key=f"refund-{payment_intent}"
        )
    except StripeError as exc:
        logger.warning(
            "refund_stripe_failed", subscription_id=str(subscription.id), reason=str(exc)
        )
        raise AppError("PAYMENTS_UNAVAILABLE", UNAVAILABLE, status_code=502) from exc
    subscription.refunded_at = now
    if subscription.plan == "ten_year":
        subscription.status = "refunded"
    await record(
        db,
        context,
        "platform.refund_issued",
        entity_type="company",
        entity_id=subscription.company_id,
        after={"subscription_id": str(subscription.id), "plan": subscription.plan},
        reason=reason,
        summary=f"Full refund of the latest {subscription.plan} payment",
    )
    return str(answer.get("id", ""))
