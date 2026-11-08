"""Billing: subscriptions (tenant) and processed Stripe events (global) (plan 6.11, T16.1).

``stripe_events`` has no company column and no personal data. The webhook runs before it knows the
company, so the API role may read and add rows, never change or remove them.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision = "0044_billing"
down_revision = "0043_rules_platform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey(
                "companies.id",
                ondelete="RESTRICT",
                name=op.f("fk_subscriptions_company_id_companies"),
            ),
            nullable=False,
        ),
        sa.Column("plan", sa.String(10), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(80), nullable=True),
        sa.Column("stripe_payment_intent_id", sa.String(80), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint("plan in ('annual', 'ten_year')", name=op.f("ck_subscriptions_plan")),
        sa.CheckConstraint(
            "(plan = 'annual' and stripe_subscription_id is not null "
            "and stripe_payment_intent_id is null) or "
            "(plan = 'ten_year' and stripe_payment_intent_id is not null "
            "and stripe_subscription_id is null)",
            name=op.f("ck_subscriptions_stripe_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscriptions")),
        sa.UniqueConstraint(
            "stripe_subscription_id", name=op.f("uq_subscriptions_stripe_subscription_id")
        ),
        sa.UniqueConstraint(
            "stripe_payment_intent_id", name=op.f("uq_subscriptions_stripe_payment_intent_id")
        ),
    )
    op.create_index("ix_subscriptions_company_id", "subscriptions", ["company_id"])
    enable_tenant_rls("subscriptions")
    add_updated_at_trigger("subscriptions")

    op.create_table(
        "stripe_events",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("event_id", sa.String(255), nullable=False),
        sa.Column("type", sa.String(100), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column(
            "processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stripe_events")),
        sa.UniqueConstraint("event_id", name=op.f("uq_stripe_events_event_id")),
    )
    op.execute("GRANT SELECT, INSERT ON stripe_events TO app_user")


def downgrade() -> None:
    op.execute("REVOKE SELECT, INSERT ON stripe_events FROM app_user")
    op.drop_table("stripe_events")
    op.drop_table("subscriptions")
