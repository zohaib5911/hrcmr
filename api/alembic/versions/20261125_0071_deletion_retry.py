"""A failed company purge waits for a backoff before it is tried again (ISS-30)."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0071_deletion_retry"
down_revision = "0070_one_primary_bank_account"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "deletion_requests",
        sa.Column("failures", sa.SmallInteger(), server_default="0", nullable=False),
    )
    op.add_column("deletion_requests", sa.Column("retry_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("deletion_requests", "retry_at")
    op.drop_column("deletion_requests", "failures")
