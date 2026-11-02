"""e-mail outbox, so a message is saved before it is sent and retried if the service is down

Revision ID: 0004_email_outbox
Revises: 0003_first_terms
Create Date: 2026-11-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger

revision: str = "0004_email_outbox"
down_revision: str | None = "0003_first_terms"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_outbox",
        sa.Column("to_address", sa.String(length=320), nullable=False),
        sa.Column("template", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=10), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_error", sa.String(length=200), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_id", sa.String(length=100), nullable=True),
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
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_email_outbox_attempts")),
        sa.CheckConstraint(
            "status in ('pending', 'sent', 'failed')", name=op.f("ck_email_outbox_status")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_outbox")),
    )
    op.create_index(
        "ix_email_outbox_status_next_attempt_at",
        "email_outbox",
        ["status", "next_attempt_at"],
        unique=False,
    )
    add_updated_at_trigger("email_outbox")
    # Not about one company (a sign-up e-mail goes out before there is a company context), so no
    # tenant policy; the API's role may add and update rows, and never delete them.
    op.execute("GRANT SELECT, INSERT, UPDATE ON email_outbox TO app_user")


def downgrade() -> None:
    op.drop_index("ix_email_outbox_status_next_attempt_at", table_name="email_outbox")
    op.drop_table("email_outbox")
