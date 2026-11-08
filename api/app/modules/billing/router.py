"""Billing endpoints (plan 8.16, API item 21, T16.1): the plan, Checkout, the Billing Portal and the
Stripe webhook.

Amounts are never written here: Checkout charges the Stripe price configured for the plan
(``STRIPE_PRICE_ANNUAL`` / ``STRIPE_PRICE_TEN_YEAR``). The webhook has no session and no CSRF token
(``/webhooks/`` is exempt in ``app/core/csrf.py``); Stripe's signature is its only credential.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.schemas import RequestModel
from app.db.session import GlobalDb  # noqa: TC001  (FastAPI reads the dependency at runtime)
from app.integrations.stripe import StripeError, StripeSignatureError
from app.modules.billing import service
from app.modules.billing.models import Subscription
from app.modules.companies.models import Company
from app.modules.rbac.deps import Access, require

if TYPE_CHECKING:
    from app.integrations.stripe import Stripe

router = APIRouter(tags=["billing"])
webhook_router = APIRouter(tags=["webhooks"])
Manager = Annotated[Access, Depends(require("billing.manage"))]
logger = get_logger("app.billing")

BILLING_PATH = "/company/billing"


class BillingOut(BaseModel):
    payments_enabled: bool
    plan: str  # free | annual | ten_year
    subscription_status: str | None
    started_at: datetime | None
    ends_at: datetime | None
    cooling_off_ends_at: datetime | None
    payment_grace_ends_at: datetime | None
    cancel_at: datetime | None
    has_billing_account: bool


class CancelOut(BaseModel):
    refunded: bool  # True: the first payment was refunded and the plan ended now
    ends_at: datetime | None  # when access ends: now after a refund, else the end of the period


class CheckoutIn(RequestModel):
    plan: Literal["annual", "ten_year"]


class RedirectOut(BaseModel):
    url: str


class WebhookOut(BaseModel):
    received: bool


def _stripe(request: Request) -> Stripe:
    stripe: Stripe = request.app.state.stripe
    return stripe


def _not_set_up() -> AppError:
    return AppError("PAYMENTS_NOT_SET_UP", "Payments are not set up yet.", status_code=503)


def _unavailable(exc: StripeError) -> AppError:
    logger.warning("stripe_call_failed", reason=str(exc))
    return AppError(
        "PAYMENTS_UNAVAILABLE",
        "We could not reach our payment provider. Try again in a few minutes.",
        status_code=502,
    )


async def _company(access: Access) -> Company:
    company = await access.db.get(Company, access.company_id)
    if company is None:  # the session's company is gone
        raise AppError("UNAUTHENTICATED", "Sign in to continue.", status_code=401)
    return company


def _has_live_plan(company: Company) -> bool:
    return (
        company.plan != "free"
        and company.subscription_status in service.LIVE_STATUSES
        and (
            company.subscription_ends_at is None or company.subscription_ends_at > datetime.now(UTC)
        )
    )


@router.get("/billing/subscription", response_model=BillingOut)
async def read_subscription(request: Request, access: Manager) -> BillingOut:
    company = await _company(access)
    latest = None
    if company.stripe_subscription_id:
        latest = await service.subscription_row(
            access.db, stripe_subscription_id=company.stripe_subscription_id
        )
    return BillingOut(
        payments_enabled=_stripe(request).enabled,
        plan=company.plan,
        subscription_status=company.subscription_status,
        started_at=company.subscription_started_at,
        ends_at=company.subscription_ends_at,
        cooling_off_ends_at=company.cooling_off_ends_at,
        payment_grace_ends_at=company.payment_grace_ends_at,
        cancel_at=latest.cancel_at if isinstance(latest, Subscription) else None,
        has_billing_account=company.stripe_customer_id is not None,
    )


@router.post("/billing/checkout-session", response_model=RedirectOut)
async def create_checkout_session(
    body: CheckoutIn, request: Request, access: Manager
) -> RedirectOut:
    """A Stripe Checkout page for the plan. The plan starts when Stripe's webhook says it is paid,
    not when the browser comes back."""
    stripe = _stripe(request)
    if not stripe.enabled:
        raise _not_set_up()
    company = await _company(access)
    if _has_live_plan(company):
        raise AppError(
            "PLAN_ALREADY_ACTIVE",
            "Your plan is already active. To change plan, contact support.",
            status_code=409,
        )
    origin = request.app.state.settings.web_origin
    try:
        if company.stripe_customer_id is None:
            customer = await stripe.create_customer(
                company_id=str(company.id), name=company.name, email=company.contact_email
            )
            company.stripe_customer_id = str(customer["id"])
            # Kept even if Checkout fails next, so the company never gets a second customer.
            await access.db.commit()
        session = await stripe.create_checkout_session(
            company_id=str(company.id),
            customer=company.stripe_customer_id,
            plan=body.plan,
            success_url=f"{origin}{BILLING_PATH}?checkout=success",
            cancel_url=f"{origin}{BILLING_PATH}?checkout=cancelled",
            idempotency_key=f"checkout-{company.id}-{uuid.uuid4()}",
        )
    except StripeError as exc:
        raise _unavailable(exc) from exc
    await access.audit(
        "billing.checkout_started",
        entity_type="company",
        entity_id=company.id,
        after={"plan": body.plan},
    )
    await access.db.commit()
    return RedirectOut(url=str(session["url"]))


@router.post("/billing/portal-session", response_model=RedirectOut)
async def create_portal_session(request: Request, access: Manager) -> RedirectOut:
    """Stripe's Billing Portal: card details and invoices. Cancelling is done on our billing page,
    so the 14-day refund rule applies (the portal's own cancel is switched off in Stripe)."""
    stripe = _stripe(request)
    if not stripe.enabled:
        raise _not_set_up()
    company = await _company(access)
    if company.stripe_customer_id is None:
        raise AppError(
            "NO_BILLING_ACCOUNT",
            "There are no payment details for this company yet.",
            status_code=409,
        )
    origin = request.app.state.settings.web_origin
    try:
        portal = await stripe.create_portal_session(
            customer=company.stripe_customer_id,
            return_url=f"{origin}{BILLING_PATH}",
            idempotency_key=f"portal-{company.id}-{uuid.uuid4()}",
        )
    except StripeError as exc:
        raise _unavailable(exc) from exc
    return RedirectOut(url=str(portal["url"]))


@router.post("/billing/cancel", response_model=CancelOut)
async def cancel_plan(request: Request, access: Manager) -> CancelOut:
    """Cancels the plan. Within 14 days of the start: a full refund through Stripe, and the plan
    ends now. After that: an annual plan ends at the end of its period, with no refund."""
    stripe = _stripe(request)
    if not stripe.enabled:
        raise _not_set_up()
    company = await _company(access)
    if not _has_live_plan(company):
        raise AppError("NO_PLAN_TO_CANCEL", "There is no active plan to cancel.", status_code=409)
    try:
        done = await service.cancel_plan(
            access.db, stripe, company, access.audit_context, now=datetime.now(UTC)
        )
    except service.CancelError as exc:
        raise AppError(exc.code, exc.message, status_code=409) from exc
    except StripeError as exc:
        raise _unavailable(exc) from exc
    return CancelOut(refunded=done.refunded, ends_at=done.ends_at)


@webhook_router.post("/webhooks/stripe", response_model=WebhookOut)
async def stripe_webhook(request: Request, db: GlobalDb) -> WebhookOut:
    """Stripe's events. Verified on the raw body; each event id is applied once."""
    stripe = _stripe(request)
    if not stripe.webhooks_enabled:
        raise _not_set_up()
    payload = await request.body()
    try:
        event = stripe.construct_event(payload, request.headers.get("stripe-signature"))
    except StripeSignatureError as exc:
        logger.warning("stripe_signature_rejected", reason=str(exc))
        raise AppError(
            "WEBHOOK_SIGNATURE_INVALID", "The signature is not valid.", status_code=400
        ) from exc
    try:
        outcome = await service.handle_event(
            db, stripe, event, payload, request.app.state.settings.web_origin
        )
    except StripeError as exc:
        # Nothing was stored, so Stripe's retry will apply it once Stripe answers again.
        raise _unavailable(exc) from exc
    logger.info("stripe_event", event_id=event["id"], type=event.get("type"), outcome=outcome)
    return WebhookOut(received=True)
