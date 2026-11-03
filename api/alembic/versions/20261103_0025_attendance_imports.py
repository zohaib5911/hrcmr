"""Reviewed attendance import snapshots and tenant file references (T9.2).
Revision ID: 0025_attendance_imports
Revises: 0024_leave_year_end
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision = "0025_attendance_imports"
down_revision = "0024_leave_year_end"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_files_company_id_id", "files", ["company_id", "id"])
    op.create_table(
        "attendance_imports",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("uuid_generate_v7()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("from_date", sa.Date()),
        sa.Column("to_date", sa.Date()),
        sa.Column("rows_total", sa.Integer(), nullable=False),
        sa.Column("rows_valid", sa.Integer(), nullable=False),
        sa.Column("rows", JSONB(), nullable=False),
        sa.Column("errors", JSONB(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="previewed"),
        sa.Column("committed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
        sa.ForeignKeyConstraint(
            ["company_id", "file_id"],
            ["files.company_id", "files.id"],
            name="fk_attendance_imports_company_file",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("status in ('previewed','committed')", name="status"),
        sa.CheckConstraint(
            "rows_total > 0 AND rows_valid >= 0 AND rows_valid <= rows_total", name="rows"
        ),
        sa.CheckConstraint(
            "(from_date is null and to_date is null) or (from_date is not null and to_date is not null and to_date >= from_date)",
            name="dates",
        ),
        sa.CheckConstraint(
            "(status='previewed' and committed_at is null) or (status='committed' and committed_at is not null)",
            name="committed",
        ),
    )
    op.create_index("ix_attendance_imports_company_id", "attendance_imports", ["company_id"])
    enable_tenant_rls("attendance_imports")
    add_updated_at_trigger("attendance_imports")


def downgrade() -> None:
    op.drop_table("attendance_imports")
    op.drop_constraint("uq_files_company_id_id", "files", type_="unique")
