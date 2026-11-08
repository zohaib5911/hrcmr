"""Who may write: an active paid plan (plan 8.16, T16.2).

A company on the free plan, or whose paid plan has lapsed, is read-only. Every write is refused with
``402 PLAN_REQUIRED`` except the ones a read-only company still needs: billing (to pay), the company
profile, the data export and account deletion. Signing in and the person's own account are under
``/auth``, which is never gated. Nothing is deleted when a plan lapses.

* Annual: Stripe's subscription status decides (Stripe moves it on at renewal). A failed renewal
  (``past_due``) keeps working for 7 days from the first failure, then becomes read-only until the
  card is fixed.
* 10-year: until its end date.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.companies.models import Company

GRACE = timedelta(days=7)
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# Writes a read-only company may still make (plan 8.16: "except auth, profile, billing, export and
# deletion").
UNGATED_PERMISSIONS = frozenset(
    {"billing.manage", "company.profile.write", "company.export", "company.delete"}
)


def is_entitled(
    company: Company, now: datetime | None = None, *, include_comp: bool = True
) -> bool:
    """May the company write now. A complimentary end date (``comp_until``, T17.6) counts for any
    plan; the paid count in the platform metrics leaves it out (``include_comp=False``)."""
    moment = now or datetime.now(UTC)
    if include_comp and company.comp_until is not None and company.comp_until > moment:
        return True
    status = company.subscription_status
    if company.plan == "ten_year":
        return status == "active" and (
            company.subscription_ends_at is None or company.subscription_ends_at > moment
        )
    if company.plan == "annual":
        if status in ("active", "trialing"):
            return True
        if status == "past_due":
            grace = company.payment_grace_ends_at
            return grace is None or grace > moment
    return False


def is_gated(method: str, permission: str) -> bool:
    """Does this request need a paid plan? Writes do; a POST that only reads (revealing a field,
    marking a notification read) is named by a ``.read`` permission and does not."""
    return (
        method.upper() in WRITE_METHODS
        and permission not in UNGATED_PERMISSIONS
        and not permission.endswith(".read")
    )
