"""Draft/published rota weeks and scheduled shifts (T9.5).

Revision ID: 0028_rota_weeks
Revises: 0027_rota_settings
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision = "0028_rota_weeks"
down_revision = "0027_rota_settings"
branch_labels = None
depends_on = None


def _common() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("uuid_generate_v7()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
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
        "rota_weeks",
        *_common(),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="draft"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("published_by", sa.Uuid()),
        sa.Column("published_shifts", JSONB(), nullable=False, server_default="[]"),
        sa.UniqueConstraint("company_id", "week_start", name="uq_rota_week_start"),
        sa.UniqueConstraint("company_id", "id", name="uq_rota_weeks_company_id_id"),
        sa.CheckConstraint("extract(isodow from week_start)=1", name="monday"),
        sa.CheckConstraint("status in ('draft','published') AND version>=0", name="state"),
    )
    op.create_table(
        "scheduled_shifts",
        *_common(),
        sa.Column("rota_week_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unpaid_break_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("shift_type_id", sa.Uuid()),
        sa.Column("note", sa.Text()),
        sa.ForeignKeyConstraint(
            ["company_id", "rota_week_id"],
            ["rota_weeks.company_id", "rota_weeks.id"],
            name="fk_scheduled_shift_week",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "employee_id"],
            ["employees.company_id", "employees.id"],
            name="fk_scheduled_shift_employee",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "shift_type_id"],
            ["shift_types.company_id", "shift_types.id"],
            name="fk_scheduled_shift_type",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "ends_at > starts_at AND unpaid_break_minutes >= 0 AND unpaid_break_minutes * interval '1 minute' <= ends_at-starts_at",
            name="duration",
        ),
    )
    for table in ("rota_weeks", "scheduled_shifts"):
        op.create_index(f"ix_{table}_company_id", table, ["company_id"])
        enable_tenant_rls(table)
        add_updated_at_trigger(table)
    op.create_index("ix_scheduled_shifts_employee_id", "scheduled_shifts", ["employee_id"])
    op.create_index("ix_scheduled_shifts_date", "scheduled_shifts", ["date"])


def downgrade() -> None:
    op.drop_table("scheduled_shifts")
    op.drop_table("rota_weeks")
