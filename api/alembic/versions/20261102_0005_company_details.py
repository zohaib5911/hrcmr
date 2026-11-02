"""company details: the fixed lists get CHECK constraints, and the AI switch

Revision ID: 0005_company_details
Revises: 0004_email_outbox
Create Date: 2026-11-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.modules.companies.reference import (
    LEGAL_STRUCTURES,
    SECTORS,
    TRADING_PERIODS,
    check_sql,
)

revision: str = "0005_company_details"
down_revision: str | None = "0004_email_outbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHECKS = (
    ("type_of_organisation", LEGAL_STRUCTURES),
    ("trading_period", TRADING_PERIODS),
    ("sector", SECTORS),
)


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("ai_features_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    for column, values in CHECKS:
        op.create_check_constraint(
            op.f(f"ck_companies_{column}"), "companies", check_sql(column, values)
        )


def downgrade() -> None:
    for column, _ in reversed(CHECKS):
        op.drop_constraint(op.f(f"ck_companies_{column}"), "companies", type_="check")
    op.drop_column("companies", "ai_features_enabled")
