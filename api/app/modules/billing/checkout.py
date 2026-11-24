"""Serialize Checkout, retaining the same provider request after an ambiguous response."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.core.errors import AppError
from app.integrations.stripe import StripeError
from app.modules.billing.models import CheckoutAttempt
from app.modules.billing.service import BILLING_PAGE, LIVE_STATUSES
from app.modules.companies.models import Company

if TYPE_CHECKING:
    from app.integrations.stripe import Stripe
    from app.modules.rbac.deps import Access


def _pending() -> AppError:
    return AppError(
        "CHECKOUT_PENDING",
        "Your previous payment is still being confirmed. Contact support if this continues.",
        status_code=409,
    )


async def _lock_company(access: Access) -> Company:
    company = await access.db.get(
        Company, access.company_id, with_for_update=True, populate_existing=True
    )
    if company is None or company.status != "active":
        raise AppError("ACCOUNT_SUSPENDED", "This account is not active.", status_code=403)
    if (
        company.plan != "free"
        and company.subscription_status in LIVE_STATUSES
        and (
            company.subscription_ends_at is None or company.subscription_ends_at > datetime.now(UTC)
        )
    ):
        raise AppError(
            "PLAN_ALREADY_ACTIVE",
            "Your plan is already active. To change plan, contact support.",
            status_code=409,
        )
    return company


async def _provider_session(
    access: Access, stripe: Stripe, attempt: CheckoutAttempt
) -> dict[str, Any]:
    if attempt.stripe_session_id:
        return await stripe.retrieve_checkout_session(attempt.stripe_session_id)
    # After Stripe may prune the key, replay could create a second purchase. Fail closed.
    if datetime.now(UTC) - attempt.created_at >= timedelta(hours=23):
        raise _pending()
    form = attempt.request_data
    live = await stripe.create_checkout_session(
        company_id=str(access.company_id),
        customer=form["customer"],
        plan=form["plan"],
        success_url=form["success_url"],
        cancel_url=form["cancel_url"],
        price_id=form["price_id"],
        attempt_id=str(attempt.id),
        idempotency_key=f"checkout-{access.company_id}-{attempt.id}",
    )
    attempt.stripe_session_id = str(live["id"])
    return live


def _open_url(live: dict[str, Any]) -> str:
    url = live.get("url")
    if live.get("status") != "open" or not isinstance(url, str) or not url:
        raise _pending()
    return url


async def start(access: Access, stripe: Stripe, plan: str, origin: str) -> str:
    db = access.db
    company = await _lock_company(access)
    attempt = await db.scalar(select(CheckoutAttempt).where(CheckoutAttempt.closed_at.is_(None)))
    if attempt is not None:
        live = await _provider_session(access, stripe, attempt)
        status = live.get("status")
        if status == "open" and attempt.request_data["plan"] == plan:
            return _open_url(live)
        if status == "open":
            if attempt.stripe_session_id is None:
                raise _pending()
            try:
                live = await stripe.expire_checkout_session(attempt.stripe_session_id)
            except StripeError:
                # The customer may have completed it while we tried to expire it.
                live = await stripe.retrieve_checkout_session(attempt.stripe_session_id)
            status = live.get("status")
        if status != "expired":
            raise _pending()
        attempt.closed_at = datetime.now(UTC)
        await db.flush()
    if company.stripe_customer_id is None:
        customer = await stripe.create_customer(
            company_id=str(company.id), name=company.name, email=company.contact_email
        )
        company.stripe_customer_id = str(customer["id"])
    attempt = CheckoutAttempt(
        company_id=company.id,
        request_data={
            "customer": company.stripe_customer_id,
            "plan": plan,
            "price_id": stripe.price_for(plan),
            "success_url": f"{origin}{BILLING_PAGE}?checkout=success",
            "cancel_url": f"{origin}{BILLING_PAGE}?checkout=cancelled",
        },
    )
    db.add(attempt)
    await db.flush()
    ident = attempt.id
    # The reservation survives a crash between Stripe accepting it and the response being saved.
    await db.commit()
    await _lock_company(access)
    attempt = await db.get(CheckoutAttempt, ident, populate_existing=True)
    if attempt is None or attempt.closed_at is not None:
        raise _pending()
    return _open_url(await _provider_session(access, stripe, attempt))
