"""SOC checks: a saved sponsorship checker run with the code the user confirmed (plan 6.10, T15.6)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision = "0042_soc_checks"
down_revision = "0041_soc_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "soc_checks",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("uuid_generate_v7()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(12), nullable=False, server_default="draft"),
        sa.Column("job_title", sa.String(200), nullable=False),
        sa.Column("job_description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "soc_code",
            sa.String(4),
            sa.ForeignKey("soc_unit_groups.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("soc_title", sa.Text(), nullable=False),
        sa.Column(
            "rules_version_id",
            sa.Uuid(),
            sa.ForeignKey("rules_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("rules_version_name", sa.String(200), nullable=False),
        sa.Column("rules_effective_from", sa.Date(), nullable=False),
        sa.Column("inputs", JSONB(), nullable=False),
        sa.Column("result", JSONB(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("confirmed_by", sa.Uuid()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
        sa.CheckConstraint("status in ('draft', 'confirmed')", name="status"),
        sa.CheckConstraint("soc_code ~ '^[1-9][0-9]{3}$'", name="soc_code"),
        sa.CheckConstraint(
            "(status = 'confirmed') = (confirmed_at is not null)", name="confirmed_at"
        ),
    )
    op.create_index("ix_soc_checks_company_id", "soc_checks", ["company_id"])
    enable_tenant_rls("soc_checks")
    add_updated_at_trigger("soc_checks")


def downgrade() -> None:
    op.drop_table("soc_checks")
