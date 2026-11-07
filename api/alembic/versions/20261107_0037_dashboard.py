"""The set-up checklist's dismissal per person (plan 8.2)."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision = "0037_dashboard"
down_revision = "0036_certificates"
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
    op.create_table(
        "onboarding_dismissals",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("uuid_generate_v7()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=False),
        *_record_columns(),
        sa.UniqueConstraint("company_id", "user_id", name="uq_onboarding_dismissals_company_user"),
    )
    enable_tenant_rls("onboarding_dismissals")
    add_updated_at_trigger("onboarding_dismissals")


def downgrade() -> None:
    op.drop_table("onboarding_dismissals")
