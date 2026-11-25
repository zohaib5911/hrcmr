"""Serialize Checkout, retaining the same provider request after an ambiguous response.

The platform takes at most ``SUBSCRIPTION_LIMIT`` subscriptions. A company with a live paid plan
holds a place, and so does a company whose Stripe Checkout is open (``checkout_reserved_until``), so
two companies paying at the same moment cannot both take the last place. The count runs under one
platform-wide lock. Renewals of plans already held are never refused.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, or_, select

from app.core.errors import AppError
from app.integrations.stripe import StripeError
from app.modules.billing.models import CheckoutAttempt
from app.modules.billing.service import BILLING_PAGE, LIVE_STATUSES
from app.modules.companies.models import Company

if TYPE_CHECKING:
    from app.integrations.stripe import Stripe
    from app.modules.rbac.deps import Access

SUBSCRIPTION_LIMIT = 2000  # the owner's ceiling for the whole platform (decided 2026-11-25)
RESERVATION = timedelta(hours=24)  # as long as a Stripe Checkout session can stay open


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


def _full() -> AppError:
    return AppError(
        "SUBSCRIPTIONS_FULL",
        "We are not taking new subscriptions at the moment. Contact support to join the waiting "
        "list.",
        status_code=409,
    )


async def _places_held(access: Access, company: Company, now: datetime) -> int:
    """Places other companies hold: a live paid plan, or a Stripe Checkout still open."""
    live = (
        (Company.plan != "free")
        & Company.subscription_status.in_(LIVE_STATUSES)
        & or_(Company.subscription_ends_at.is_(None), Company.subscription_ends_at > now)
    )
    held = await access.db.scalar(
        select(func.count(Company.id)).where(
            Company.id != company.id, or_(live, Company.checkout_reserved_until > now)
        )
    )
    return int(held or 0)


async def _take_place(access: Access, company: Company) -> None:
    """Refuse a new purchase once every place is held, else hold one. Called inside the transaction
    that records the reservation, so the platform lock is held until that commit."""
    now = datetime.now(UTC)
    await access.db.execute(
        select(func.pg_advisory_xact_lock(func.hashtextextended("subscription-places", 0)))
    )
    if await _places_held(access, company, now) >= SUBSCRIPTION_LIMIT:
        raise _full()
    company.checkout_reserved_until = now + RESERVATION


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
        company.checkout_reserved_until = None
        await db.flush()
    # Fail fast before any Stripe call; the locked check below is the one that holds the place.
    if await _places_held(access, company, datetime.now(UTC)) >= SUBSCRIPTION_LIMIT:
        raise _full()
    if company.stripe_customer_id is None:
        customer = await stripe.create_customer(
            company_id=str(company.id), name=company.name, email=company.contact_email
        )
        company.stripe_customer_id = str(customer["id"])
    await _take_place(access, company)
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
