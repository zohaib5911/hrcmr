"""Audited immutable leave-year close snapshots (T8.5).
Revision ID: 0024_leave_year_end
Revises: 0023_leave_requests
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision = "0024_leave_year_end"
down_revision = "0023_leave_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leave_year_end_runs",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("uuid_generate_v7()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("from_year", sa.Date(), nullable=False),
        sa.Column("to_year", sa.Date(), nullable=False),
        sa.Column("run_by", sa.Uuid(), nullable=False),
        sa.Column("overrides", JSONB(), nullable=False),
        sa.Column("preview_token", sa.String(64), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
        sa.UniqueConstraint("company_id", "from_year", name="uq_leave_year_end_runs_company_year"),
        sa.CheckConstraint("to_year > from_year", name="years"),
    )
    op.create_index("ix_leave_year_end_runs_company_id", "leave_year_end_runs", ["company_id"])
    enable_tenant_rls("leave_year_end_runs")
    add_updated_at_trigger("leave_year_end_runs")
    op.execute("""CREATE FUNCTION leave_year_end_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Leave year-end runs are immutable' USING ERRCODE = '23514'; END; $$""")
    op.execute("""CREATE TRIGGER trg_leave_year_end_immutable BEFORE UPDATE OR DELETE ON leave_year_end_runs
    FOR EACH ROW EXECUTE FUNCTION leave_year_end_immutable()""")


def downgrade() -> None:
    op.drop_table("leave_year_end_runs")
    op.execute("DROP FUNCTION leave_year_end_immutable()")
