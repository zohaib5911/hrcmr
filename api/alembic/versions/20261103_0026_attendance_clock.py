"""Consent-gated clock locations and weekly timesheet approvals (T9.3).

Revision ID: 0026_attendance_clock
Revises: 0025_attendance_imports
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision = "0026_attendance_clock"
down_revision = "0025_attendance_imports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column(
            "clock_geolocation_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.create_index(
        "uq_attendance_open_clock",
        "attendance_records",
        ["company_id", "employee_id"],
        unique=True,
        postgresql_where=sa.text("source='clock' and clock_in is not null and clock_out is null"),
    )
    op.create_table(
        "timesheet_approvals",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("uuid_generate_v7()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
        sa.ForeignKeyConstraint(
            ["company_id", "employee_id"],
            ["employees.company_id", "employees.id"],
            name="fk_timesheet_company_employee",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "company_id", "employee_id", "period_start", name="uq_timesheet_employee_week"
        ),
        sa.CheckConstraint("period_end = period_start + 6", name="period"),
    )
    op.create_index("ix_timesheet_approvals_company_id", "timesheet_approvals", ["company_id"])
    enable_tenant_rls("timesheet_approvals")
    add_updated_at_trigger("timesheet_approvals")


def downgrade() -> None:
    op.drop_table("timesheet_approvals")
    op.drop_index("uq_attendance_open_clock", table_name="attendance_records")
    op.drop_column("companies", "clock_geolocation_enabled")
