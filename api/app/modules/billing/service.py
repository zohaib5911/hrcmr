"""Applying Stripe's webhook events to a company (plan 8.16, T16.1).

Each event is handled once: its id is stored in ``stripe_events`` in the same transaction as the
change it makes, so a replay or a second delivery finds the id and does nothing, and a failure part
way rolls back both (Stripe then delivers it again).

The API role cannot see companies without being scoped to one, so the company is taken from the
event: Checkout sessions, subscriptions and payments carry ``metadata.company_id`` (set by us when
the session was made), and for anything else the Stripe customer's metadata is asked for. The event
is signed by Stripe, and the customer must be the one the company holds, so the id is trusted.

Subscriptions are read back from Stripe instead of taken from the event body. Events can arrive out
of order; the live subscription is always the latest state.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.crypto import encrypt
from app.core.logging import get_logger
from app.modules.audit.service import AuditContext, record
from app.modules.billing.entitlements import GRACE
from app.modules.billing.models import CheckoutAttempt, PaymentRefund, StripeEvent, Subscription
from app.modules.companies.models import Company
from app.modules.email.models import EmailOutbox
from app.modules.email.outbox import PAYLOAD_CONTEXT
from app.modules.email.templates import check
from app.modules.identity.models import Membership, User
from app.modules.notifications.models import Notification

if TYPE_CHECKING:
    from app.db.session import GlobalSession, TenantSession
    from app.integrations.stripe import Stripe

logger = get_logger("app.billing")

COOLING_OFF = timedelta(days=14)
TEN_YEARS = 10
# Stripe statuses in which an annual plan is still the company's plan. ``past_due`` is a failed
# renewal still being retried; the grace period for it is T16.2's.
LIVE_STATUSES = frozenset({"active", "trialing", "past_due"})
HANDLED = frozenset(
    {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
        "checkout.session.async_payment_failed",
        "invoice.paid",
        "invoice.payment_failed",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "charge.refunded",
    }
)
SUMMARY = ("plan", "subscription_status", "subscription_ends_at", "payment_grace_ends_at")
BILLING_PAGE = "/company/billing"


def _when(seconds: Any) -> datetime | None:
    return datetime.fromtimestamp(int(seconds), UTC) if seconds else None


def _plus_years(moment: datetime, years: int) -> datetime:
    try:
        return moment.replace(year=moment.year + years)
    except ValueError:  # 29 February in a year that has none
        return moment.replace(year=moment.year + years, day=28)


def _id(value: Any) -> str | None:
    """A Stripe reference is an id, or the object itself when it was expanded."""
    if isinstance(value, dict):
        value = value.get("id")
    return value if isinstance(value, str) and value else None


def _company_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value)) if value else None
    except ValueError:
        return None


def _invoice_subscription(invoice: dict[str, Any]) -> str | None:
    # Stripe moved this under ``parent`` in 2025; older API versions have it at the top.
    parent = (invoice.get("parent") or {}).get("subscription_details") or {}
    return _id(parent.get("subscription")) or _id(invoice.get("subscription"))


def _metadata_company(obj: dict[str, Any]) -> uuid.UUID | None:
    found = _company_uuid((obj.get("metadata") or {}).get("company_id"))
    if found is None and obj.get("object") == "checkout.session":
        found = _company_uuid(obj.get("client_reference_id"))
    if found is None and obj.get("object") == "invoice":
        details = (obj.get("parent") or {}).get("subscription_details") or obj.get(
            "subscription_details"
        )
        found = _company_uuid(((details or {}).get("metadata") or {}).get("company_id"))
    return found


async def _company_for(stripe: Stripe, obj: dict[str, Any]) -> uuid.UUID | None:
    found = _metadata_company(obj)
    if found is not None:
        return found
    customer = _id(obj.get("customer"))
    if customer is None:
        return None
    return _company_uuid(
        ((await stripe.retrieve_customer(customer)).get("metadata") or {}).get("company_id")
    )


def summary(company: Company) -> dict[str, Any]:
    return {name: getattr(company, name) for name in SUMMARY}


async def handle_event(
    db: GlobalSession, stripe: Stripe, event: dict[str, Any], payload: bytes, web_origin: str
) -> str:
    """Applies one verified event. Returns what happened: ``applied``, ``duplicate`` or
    ``ignored`` (a type we do not act on, or an object that is not one of our companies')."""
    stored = await db.execute(
        insert(StripeEvent)
        .values(
            event_id=event["id"],
            type=str(event.get("type", ""))[:100],
            payload_hash=hashlib.sha256(payload).hexdigest(),
        )
        .on_conflict_do_nothing(index_elements=["event_id"])
        .returning(StripeEvent.id)
    )
    if stored.scalar_one_or_none() is None:
        await db.rollback()
        return "duplicate"
    kind = event.get("type")
    obj: dict[str, Any] = (event.get("data") or {}).get("object") or {}
    outcome = "ignored"
    if kind in HANDLED:
        company_id = await _company_for(stripe, obj)
        if company_id is not None:
            await db.scope_to_company(company_id)
            company = await db.get(
                Company, company_id, with_for_update=True, populate_existing=True
            )
            if company is not None and _belongs(company, obj):
                await _apply(db, stripe, company, str(kind), obj, event, web_origin)
                outcome = "applied"
    if outcome == "ignored":
        logger.info("stripe_event_ignored", event_id=event["id"], type=kind)
    await db.commit()
    return outcome


def _belongs(company: Company, obj: dict[str, Any]) -> bool:
    """The object's customer is the company's (or the company has none yet)."""
    customer = _id(obj.get("customer"))
    if customer is None or company.stripe_customer_id in (None, customer):
        return True
    logger.warning("stripe_customer_mismatch", company_id=str(company.id))
    return False


async def _apply(
    db: GlobalSession,
    stripe: Stripe,
    company: Company,
    kind: str,
    obj: dict[str, Any],
    event: dict[str, Any],
    web_origin: str,
) -> None:
    before = summary(company)
    customer = _id(obj.get("customer"))
    if customer and company.stripe_customer_id is None:
        company.stripe_customer_id = customer
    action = "billing.subscription_updated"
    if kind.startswith("checkout.session."):
        attempt_id = _company_uuid((obj.get("metadata") or {}).get("checkout_attempt_id"))
        attempt = await db.get(CheckoutAttempt, attempt_id) if attempt_id is not None else None
        if kind == "checkout.session.async_payment_failed":
            if attempt is not None:
                attempt.closed_at = datetime.now(UTC)
            return
        if obj.get("payment_status") not in ("paid", "no_payment_required"):
            return  # a delayed payment method: nothing is bought until it is paid
        if attempt is not None:
            attempt.closed_at = datetime.now(UTC)
        action = "billing.plan_purchased"
        if obj.get("mode") == "subscription" and _id(obj.get("subscription")):
            await _sync_subscription(db, stripe, company, str(_id(obj.get("subscription"))))
        elif obj.get("mode") == "payment" and _id(obj.get("payment_intent")):
            await _ten_year_paid(db, company, str(_id(obj.get("payment_intent"))), event)
    elif kind in ("invoice.paid", "invoice.payment_failed"):
        subscription = _invoice_subscription(obj)
        if subscription:
            await _sync_subscription(db, stripe, company, subscription)
        if kind == "invoice.payment_failed":
            action = "billing.payment_failed"
            await _start_grace(db, company, event, web_origin)
    elif kind.startswith("customer.subscription."):
        await _sync_subscription(db, stripe, company, str(_id(obj.get("id"))))
    elif kind == "charge.refunded":
        action = "billing.refunded"
        if not await _refunded(db, company, obj, event):
            return
    after = summary(company)
    if after != before or action != "billing.subscription_updated":
        await record(
            db,
            AuditContext(company_id=company.id, actor_user_id=None, actor_type="system"),
            action,
            entity_type="company",
            entity_id=company.id,
            before=before,
            after=after,
            summary=f"Stripe event {kind}",
        )


async def subscription_row(
    db: GlobalSession | TenantSession, **stripe_id: str
) -> Subscription | None:
    ((column, value),) = stripe_id.items()
    found: Subscription | None = (
        await db.execute(select(Subscription).where(getattr(Subscription, column) == value))
    ).scalar_one_or_none()
    return found


async def _sync_subscription(
    db: GlobalSession | TenantSession, stripe: Stripe, company: Company, subscription_id: str
) -> None:
    """Copy the live Stripe subscription onto its row and, if it is the company's plan, onto the
    company."""
    live = await stripe.retrieve_subscription(subscription_id)
    item = ((live.get("items") or {}).get("data") or [{}])[0]
    # The period moved from the subscription to its items in Stripe's 2025 API versions.
    start = _when(live.get("current_period_start") or item.get("current_period_start"))
    end = _when(live.get("current_period_end") or item.get("current_period_end"))
    cancel_at = _when(live.get("cancel_at")) or (end if live.get("cancel_at_period_end") else None)
    status = str(live.get("status", "incomplete"))
    row = await subscription_row(db, stripe_subscription_id=subscription_id)
    if row is None:
        row = Subscription(
            company_id=company.id,
            plan="annual",
            status=status,
            stripe_subscription_id=subscription_id,
        )
        db.add(row)
    row.status = status
    row.current_period_start = start
    row.current_period_end = end
    row.cancel_at = cancel_at
    await db.flush()
    # A company on the 10-year plan, or on a newer subscription, keeps it.
    if company.plan == "ten_year" and company.subscription_status in LIVE_STATUSES:
        return
    if company.stripe_subscription_id not in (None, subscription_id) and (
        company.subscription_status in LIVE_STATUSES
    ):
        return
    started = _when(live.get("start_date")) or start
    company.stripe_subscription_id = subscription_id
    company.subscription_status = status
    company.subscription_ends_at = end
    if status in ("active", "trialing"):
        company.payment_grace_ends_at = None  # paid again: the grace period is over
    if status in LIVE_STATUSES:
        company.plan = "annual"
        if started and company.subscription_started_at != started:
            company.subscription_started_at = started
            company.cooling_off_ends_at = started + COOLING_OFF
    elif status in ("canceled", "incomplete_expired", "unpaid"):
        company.plan = "free"
        company.subscription_ends_at = _when(live.get("ended_at")) or end


async def _ten_year_paid(
    db: GlobalSession, company: Company, payment_intent: str, event: dict[str, Any]
) -> None:
    # An earlier-delivered refund is authoritative even when no purchase row existed yet.
    refund = await db.scalar(
        select(PaymentRefund).where(PaymentRefund.stripe_payment_intent_id == payment_intent)
    )
    if refund is not None:
        return
    paid_at = _when(event.get("created")) or datetime.now(UTC)
    ends = _plus_years(paid_at, TEN_YEARS)
    row = await subscription_row(db, stripe_payment_intent_id=payment_intent)
    if row is None:
        row = Subscription(
            company_id=company.id,
            plan="ten_year",
            status="active",
            stripe_payment_intent_id=payment_intent,
            current_period_start=paid_at,
            current_period_end=ends,
        )
        db.add(row)
        await db.flush()
    if row.refunded_at is not None:
        return
    company.plan = "ten_year"
    company.subscription_status = "active"
    company.subscription_started_at = row.current_period_start
    company.subscription_ends_at = row.current_period_end
    company.cooling_off_ends_at = (row.current_period_start or paid_at) + COOLING_OFF


async def _refunded(
    db: GlobalSession, company: Company, charge: dict[str, Any], event: dict[str, Any]
) -> bool:
    """A full refund of a 10-year payment ends the plan now. An annual refund is recorded; the
    subscription's cancellation (its own event) ends that plan."""
    if not charge.get("refunded"):
        return False  # a partial refund changes no plan
    refunded_at = _when(event.get("created")) or datetime.now(UTC)
    payment_intent = _id(charge.get("payment_intent"))
    if payment_intent:
        await db.execute(
            insert(PaymentRefund)
            .values(
                company_id=company.id,
                stripe_payment_intent_id=payment_intent,
                refunded_at=refunded_at,
            )
            .on_conflict_do_nothing(index_elements=["stripe_payment_intent_id"])
        )
    row = (
        await subscription_row(db, stripe_payment_intent_id=payment_intent)
        if payment_intent
        else None
    )
    if row is None and company.stripe_subscription_id:
        row = await subscription_row(db, stripe_subscription_id=company.stripe_subscription_id)
    if row is None or row.refunded_at is not None:
        return False
    row.refunded_at = refunded_at
    if row.plan == "ten_year":
        row.status = "refunded"
        if company.plan == "ten_year":
            company.plan = "free"
            company.subscription_status = "refunded"
            company.subscription_ends_at = refunded_at
    await db.flush()
    return True


async def _start_grace(
    db: GlobalSession, company: Company, event: dict[str, Any], web_origin: str
) -> None:
    """The first failed renewal starts 7 days of grace and tells the company admins. Stripe's
    later retries that fail again do not move the date or send more mail."""
    if company.plan != "annual" or company.subscription_status != "past_due":
        return  # the retry already went through, or this is not the company's plan
    if company.payment_grace_ends_at is not None:
        return
    failed_at = _when(event.get("created")) or datetime.now(UTC)
    company.payment_grace_ends_at = failed_at + GRACE
    grace_end = f"{company.payment_grace_ends_at:%-d %B %Y}"
    admins = (
        await db.execute(
            select(User)
            .join(Membership, Membership.user_id == User.id)
            .where(
                Membership.company_id == company.id,
                Membership.role == "company_admin",
                Membership.status == "active",
                User.is_active.is_(True),
            )
        )
    ).scalars()
    for user in admins:
        db.add(
            Notification(
                company_id=company.id,
                user_id=user.id,
                kind="billing.payment_failed",
                title="Your payment did not go through",
                body=f"Update your card details by {grace_end} to keep full access.",
                link=BILLING_PAGE,
            )
        )
        # Sent whatever the e-mail preference: losing write access is an account matter.
        data = {
            "first_name": user.first_name,
            "grace_end": grace_end,
            "link": f"{web_origin}{BILLING_PAGE}",
        }
        check("payment_failed", data)
        db.add(
            EmailOutbox(
                to_address=user.email,
                template="payment_failed",
                payload=encrypt(json.dumps(data), context=PAYLOAD_CONTEXT),
            )
        )


ENDED = frozenset({"canceled", "incomplete_expired"})
REFUND_NOT_FOUND = "We could not find the payment to refund. Contact support."


class CancelError(Exception):
    """The plan cannot be cancelled as asked. ``code`` is the API error code the request gets."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Cancellation:
    refunded: bool
    ends_at: datetime | None


async def cancel_plan(
    db: TenantSession,
    stripe: Stripe,
    company: Company,
    context: AuditContext,
    *,
    now: datetime,
) -> Cancellation:
    """Plan 8.16. Within 14 days of the start the first payment is refunded in full and the plan
    ends now. After 14 days an annual plan ends at the end of its period, with no refund. A 10-year
    plan does not renew, so after its 14 days there is nothing to cancel."""
    before = summary(company)
    if company.cooling_off_ends_at is not None and now < company.cooling_off_ends_at:
        await _refund_and_end(db, stripe, company, context, now=now)
        cancellation = Cancellation(refunded=True, ends_at=company.subscription_ends_at)
    elif company.plan == "annual" and company.stripe_subscription_id:
        subscription_id = company.stripe_subscription_id
        await stripe.cancel_at_period_end(
            subscription_id, idempotency_key=f"cancel-period-{subscription_id}"
        )
        await _sync_subscription(db, stripe, company, subscription_id)
        cancellation = Cancellation(refunded=False, ends_at=company.subscription_ends_at)
    else:
        raise CancelError(
            "NOTHING_TO_CANCEL",
            "This plan does not renew, so there is nothing to cancel. "
            "Contact support to end it early.",
        )
    await record(
        db,
        context,
        "billing.cancelled",
        entity_type="company",
        entity_id=company.id,
        before=before,
        after=summary(company),
        summary=(
            "Plan cancelled with a full refund"
            if cancellation.refunded
            else "Plan cancelled at the end of its period"
        ),
    )
    await db.commit()
    return cancellation


async def _refund_and_end(
    db: TenantSession,
    stripe: Stripe,
    company: Company,
    context: AuditContext,
    *,
    now: datetime,
) -> None:
    """A full refund of the first payment, then the plan ends at once. The refund is committed
    before the subscription is ended, so a retry after a failed call finds it refunded and does not
    ask Stripe again."""
    subscription_id = company.stripe_subscription_id if company.plan == "annual" else None
    if subscription_id:
        row = await subscription_row(db, stripe_subscription_id=subscription_id)
    else:
        row = await _live_ten_year(db, company)
    if row is None:
        raise CancelError("NOTHING_TO_REFUND", REFUND_NOT_FOUND)
    if row.refunded_at is None:
        if subscription_id:
            payment_intent = await _first_payment_intent(stripe, subscription_id)
        else:
            payment_intent = row.stripe_payment_intent_id
        if payment_intent is None:
            raise CancelError("NOTHING_TO_REFUND", REFUND_NOT_FOUND)
        await stripe.create_refund(
            payment_intent=payment_intent, idempotency_key=f"refund-{payment_intent}"
        )
        row.refunded_at = now
        if row.plan == "ten_year":
            row.status = "refunded"
        await record(
            db,
            context,
            "billing.refunded",
            entity_type="company",
            entity_id=company.id,
            summary="Full refund of the first payment, within the 14 days",
        )
        await db.commit()
    if subscription_id:
        live = await stripe.retrieve_subscription(subscription_id)
        if live.get("status") not in ENDED:
            await stripe.cancel_now(subscription_id)
        await _sync_subscription(db, stripe, company, subscription_id)
    else:
        company.plan = "free"
        company.subscription_status = "refunded"
        company.subscription_ends_at = now


async def _live_ten_year(db: TenantSession, company: Company) -> Subscription | None:
    return (
        (
            await db.execute(
                select(Subscription).where(
                    Subscription.company_id == company.id,
                    Subscription.plan == "ten_year",
                    Subscription.refunded_at.is_(None),
                )
            )
        )
        .scalars()
        .first()
    )


async def _first_payment_intent(stripe: Stripe, subscription_id: str) -> str | None:
    """The payment behind the subscription's latest invoice (the first one, within 14 days)."""
    live = await stripe.retrieve_subscription(subscription_id)
    invoice_id = _id(live.get("latest_invoice"))
    if invoice_id is None:
        return None
    invoice = await stripe.retrieve_invoice(invoice_id)
    direct = _id(invoice.get("payment_intent"))
    if direct:
        return direct
    # Stripe's 2025 API versions list an invoice's payments under ``payments``.
    for entry in (invoice.get("payments") or {}).get("data") or []:
        intent = _id((entry.get("payment") or {}).get("payment_intent"))
        if entry.get("status") == "paid" and intent:
            return intent
    return None
