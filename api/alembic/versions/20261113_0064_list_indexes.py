"""Indexes for the main lists at 1,000 employees (T22.2): the employee list by name, leave requests
newest first and attendance by date. EXPLAIN checks in tests/db/test_performance.py."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0064_list_indexes"
down_revision = "0063_register_companies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_employees_company_id_name",
        "employees",
        ["company_id", sa.text("lower(last_name)"), sa.text("lower(first_name)")],
    )
    op.create_index(
        "ix_leave_requests_company_id_start_date",
        "leave_requests",
        ["company_id", "start_date", "id"],
    )
    op.create_index(
        "ix_attendance_records_company_id_date", "attendance_records", ["company_id", "date"]
    )


def downgrade() -> None:
    op.drop_index("ix_attendance_records_company_id_date", "attendance_records")
    op.drop_index("ix_leave_requests_company_id_start_date", "leave_requests")
    op.drop_index("ix_employees_company_id_name", "employees")
