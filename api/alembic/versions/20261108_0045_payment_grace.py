"""Payment grace: when a failed annual renewal makes the company read-only (plan 8.16, T16.2)."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0045_payment_grace"
down_revision = "0044_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "companies", sa.Column("payment_grace_ends_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("companies", "payment_grace_ends_at")
