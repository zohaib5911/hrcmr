"""trading hours: when the business is open on each weekday

Revision ID: 0010_trading_hours
Revises: 0009_holidays
Create Date: 2026-11-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision: str = "0010_trading_hours"
down_revision: str | None = "0009_holidays"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trading_hours_days",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("is_open", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("opens_at", sa.Time(), nullable=True),
        sa.Column("closes_at", sa.Time(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint("weekday between 1 and 7", name=op.f("ck_trading_hours_days_weekday")),
        sa.CheckConstraint(
            "(is_open and opens_at is not null and closes_at is not null and opens_at < closes_at)"
            " or (not is_open and opens_at is null and closes_at is null)",
            name=op.f("ck_trading_hours_days_times"),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_trading_hours_days_company_id_companies"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trading_hours_days")),
        sa.UniqueConstraint(
            "company_id", "weekday", name="uq_trading_hours_days_company_id_weekday"
        ),
    )
    op.create_index(
        op.f("ix_trading_hours_days_company_id"), "trading_hours_days", ["company_id"], unique=False
    )
    add_updated_at_trigger("trading_hours_days")
    enable_tenant_rls("trading_hours_days", privileges=("SELECT", "INSERT", "UPDATE"))


def downgrade() -> None:
    op.drop_table("trading_hours_days")
