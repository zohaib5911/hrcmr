"""Append-only leave movements and caller-scoped balance view (T8.2).
Revision ID: 0022_leave_ledger
Revises: 0021_leave_types
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger, create_tenant_view, enable_tenant_rls

revision = "0022_leave_ledger"
down_revision = "0021_leave_types"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "leave_types",
        sa.Column(
            "bank_holidays_included", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.execute("UPDATE leave_types SET bank_holidays_included = true WHERE seed_key = 'annual'")
    op.create_unique_constraint("uq_employees_company_id_id", "employees", ["company_id", "id"])
    op.create_unique_constraint("uq_leave_types_company_id_id", "leave_types", ["company_id", "id"])
    op.create_table(
        "leave_ledger",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("uuid_generate_v7()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("leave_type_id", sa.Uuid(), nullable=False),
        sa.Column("leave_year_start", sa.Date(), nullable=False),
        sa.Column("entry_type", sa.String(16), nullable=False),
        sa.Column("days", sa.Numeric(10, 2), nullable=False),
        sa.Column("target_days", sa.Numeric(10, 2)),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("leave_request_id", sa.Uuid()),
        sa.Column("bucket", sa.String(16)),
        sa.Column("idempotency_key", sa.Uuid()),
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
            name="fk_leave_ledger_company_employee",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "leave_type_id"],
            ["leave_types.company_id", "leave_types.id"],
            name="fk_leave_ledger_company_type",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "entry_type in ('grant','accrual','carry_over','taken','adjustment','deduct','set','year_end_expiry')",
            name="entry_type",
        ),
        sa.CheckConstraint("length(trim(reason)) > 0", name="reason"),
        sa.CheckConstraint(
            "(days <> 0 OR entry_type = 'set') AND days <> 'NaN'::numeric", name="days"
        ),
        sa.CheckConstraint(
            "(entry_type not in ('grant','accrual','carry_over') or days > 0) and (entry_type not in ('taken','deduct','year_end_expiry') or days < 0)",
            name="sign",
        ),
        sa.CheckConstraint("bucket is null or bucket in ('entitlement','calendar')", name="bucket"),
        sa.UniqueConstraint(
            "company_id", "idempotency_key", name="uq_leave_ledger_company_id_idempotency_key"
        ),
    )
    op.create_index("ix_leave_ledger_company_id", "leave_ledger", ["company_id"])
    op.create_index(
        "ix_leave_ledger_balance",
        "leave_ledger",
        ["company_id", "employee_id", "leave_type_id", "leave_year_start"],
    )
    enable_tenant_rls("leave_ledger", privileges=("SELECT", "INSERT"))
    add_updated_at_trigger("leave_ledger")
    op.execute("""CREATE FUNCTION leave_ledger_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'leave ledger is append-only'; END; $$""")
    op.execute(
        "CREATE TRIGGER trg_leave_ledger_immutable BEFORE UPDATE OR DELETE ON leave_ledger FOR EACH ROW EXECUTE FUNCTION leave_ledger_immutable()"
    )
    create_tenant_view(
        "leave_balances",
        "SELECT company_id, employee_id, leave_type_id, leave_year_start, sum(days) AS days FROM leave_ledger GROUP BY company_id, employee_id, leave_type_id, leave_year_start",
    )


def downgrade() -> None:
    op.execute("DROP VIEW leave_balances")
    op.drop_table("leave_ledger")
    op.execute("DROP FUNCTION leave_ledger_immutable()")
    op.drop_constraint("uq_leave_types_company_id_id", "leave_types", type_="unique")
    op.drop_constraint("uq_employees_company_id_id", "employees", type_="unique")
    op.drop_column("leave_types", "bank_holidays_included")
