"""Durable refund and irreversible deletion state (FIX-security-audit)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision = "0067_security_lifecycle"
down_revision = "0066_trigram_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "checkout_attempts",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("request_data", postgresql.JSONB(), nullable=False),
        sa.Column("stripe_session_id", sa.String(255)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_session_id"),
    )
    op.create_index("ix_checkout_attempts_company_id", "checkout_attempts", ["company_id"])
    op.create_index(
        "uq_checkout_attempts_open",
        "checkout_attempts",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text("closed_at IS NULL"),
    )
    enable_tenant_rls("checkout_attempts")
    add_updated_at_trigger("checkout_attempts")
    op.add_column("deletion_requests", sa.Column("started_at", sa.DateTime(timezone=True)))
    op.create_table(
        "payment_refunds",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("stripe_payment_intent_id", sa.String(80), nullable=False),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_payment_intent_id"),
    )
    op.create_index("ix_payment_refunds_company_id", "payment_refunds", ["company_id"])
    enable_tenant_rls("payment_refunds")
    add_updated_at_trigger("payment_refunds")


def downgrade() -> None:
    op.drop_table("checkout_attempts")
    op.drop_table("payment_refunds")
    op.drop_column("deletion_requests", "started_at")
