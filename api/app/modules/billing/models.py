"""Billing tables (plan 6.11, T16.1).

``subscriptions`` is one row per purchase a company makes: an annual Stripe subscription, or a
10-year one-off payment. The company row keeps the summary the rest of the app reads (plan, status,
end date); this keeps the history and the Stripe ids.

``stripe_events`` is global: Stripe event ids already handled, so a replayed or re-delivered webhook
changes nothing. It holds no company data, only the event id, type and a hash of the body.
"""

from __future__ import annotations

import uuid  # noqa: TC003  (SQLAlchemy resolves the Mapped[...] annotations at runtime)
from datetime import datetime  # noqa: TC003  (same)

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin, UUIDPrimaryKeyMixin


class Subscription(Base, RecordMixin, TenantMixin):
    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint("plan in ('annual', 'ten_year')", name="plan"),
        # An annual plan is a Stripe subscription; a 10-year plan is a single payment.
        CheckConstraint(
            "(plan = 'annual' and stripe_subscription_id is not null "
            "and stripe_payment_intent_id is null) or "
            "(plan = 'ten_year' and stripe_payment_intent_id is not null "
            "and stripe_subscription_id is null)",
            name="stripe_id",
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    plan: Mapped[str] = mapped_column(String(10), nullable=False)
    # Stripe's subscription status (active, past_due, canceled, ...), or "active" / "refunded" for
    # a 10-year payment.
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(80), unique=True)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(80), unique=True)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StripeEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "stripe_events"

    event_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
