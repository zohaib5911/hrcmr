"""Leave decisions and attendance synchronization (T8.3).
Revision ID: 0023_leave_requests
Revises: 0022_leave_ledger
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision = "0023_leave_requests"
down_revision = "0022_leave_ledger"
branch_labels = None
depends_on = None


def _common() -> list[sa.Column[object]]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("uuid_generate_v7()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
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
        "leave_requests",
        *_common(),
        sa.Column("leave_type_id", sa.Uuid(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("half_day_start", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("half_day_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("working_days", sa.Numeric(8, 2), nullable=False),
        sa.Column("working_dates", JSONB(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("decided_by", sa.Uuid()),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("decision_note", sa.Text()),
        sa.UniqueConstraint("company_id", "id", name="uq_leave_requests_company_id_id"),
        sa.ForeignKeyConstraint(
            ["company_id", "employee_id"],
            ["employees.company_id", "employees.id"],
            name="fk_leave_requests_company_employee",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "leave_type_id"],
            ["leave_types.company_id", "leave_types.id"],
            name="fk_leave_requests_company_type",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("end_date >= start_date AND end_date - start_date <= 366", name="dates"),
        sa.CheckConstraint(
            "status in ('pending','approved','rejected','cancelled')", name="status"
        ),
        sa.CheckConstraint("working_days > 0", name="working_days"),
    )
    op.create_index("ix_leave_requests_company_id", "leave_requests", ["company_id"])
    op.create_index(
        "ix_leave_requests_employee_dates",
        "leave_requests",
        ["company_id", "employee_id", "start_date", "end_date"],
    )
    op.create_table(
        "attendance_records",
        *_common(),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("clock_in", sa.DateTime(timezone=True)),
        sa.Column("clock_out", sa.DateTime(timezone=True)),
        sa.Column("unpaid_break_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hours", sa.Numeric(6, 2)),
        sa.Column("note", sa.Text()),
        sa.Column("source", sa.String(12), nullable=False, server_default="manual"),
        sa.Column("geo", JSONB()),
        sa.Column("leave_request_id", sa.Uuid()),
        sa.UniqueConstraint(
            "company_id", "employee_id", "date", name="uq_attendance_records_company_employee_date"
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "employee_id"],
            ["employees.company_id", "employees.id"],
            name="fk_attendance_records_company_employee",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "leave_request_id"],
            ["leave_requests.company_id", "leave_requests.id"],
            name="fk_attendance_records_company_leave",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status in ('present','absent','late','half_day','on_leave','sick')", name="status"
        ),
        sa.CheckConstraint(
            "source in ('manual','import','grid','clock','leave_sync')", name="source"
        ),
        sa.CheckConstraint(
            "unpaid_break_minutes >= 0 AND (hours IS NULL OR hours >= 0)", name="hours"
        ),
    )
    op.create_index("ix_attendance_records_company_id", "attendance_records", ["company_id"])
    for table in ("leave_requests", "attendance_records"):
        enable_tenant_rls(table)
        add_updated_at_trigger(table)
    op.create_foreign_key(
        "fk_leave_ledger_company_request",
        "leave_ledger",
        "leave_requests",
        ["company_id", "leave_request_id"],
        ["company_id", "id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_leave_ledger_company_request", "leave_ledger", type_="foreignkey")
    op.drop_table("attendance_records")
    op.drop_table("leave_requests")
