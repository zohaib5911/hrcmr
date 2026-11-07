"""Notification e-mail preferences, and which notifications have gone out in a digest (plan 8.2, T14.2)."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision = "0038_notification_preferences"
down_revision = "0037_dashboard"
branch_labels = None
depends_on = None


def _record_columns() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
    ]


def upgrade() -> None:
    op.add_column("notifications", sa.Column("digested_at", sa.DateTime(timezone=True)))
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("uuid_generate_v7()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("mode", sa.String(10), nullable=False),
        *_record_columns(),
        sa.UniqueConstraint(
            "company_id", "user_id", name="uq_notification_preferences_company_user"
        ),
        sa.CheckConstraint("mode in ('immediate', 'daily', 'off')", name="mode"),
    )
    enable_tenant_rls("notification_preferences")
    add_updated_at_trigger("notification_preferences")


def downgrade() -> None:
    op.drop_table("notification_preferences")
    op.drop_column("notifications", "digested_at")
