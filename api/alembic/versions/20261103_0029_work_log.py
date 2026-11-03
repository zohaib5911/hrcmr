"""Daily work log entries, retained originals and soft removal (T9.6).

Revision ID: 0029_work_log
Revises: 0028_rota_weeks
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision = "0029_work_log"
down_revision = "0028_rota_weeks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_responsibility_company_employee_id",
        "employee_responsibilities",
        ["company_id", "employee_id", "id"],
    )
    op.create_table(
        "work_log_entries",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("uuid_generate_v7()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("from_time", sa.Time(), nullable=False),
        sa.Column("to_time", sa.Time(), nullable=False),
        sa.Column("hours", sa.Numeric(6, 2), nullable=False),
        sa.Column("responsibility_id", sa.Uuid()),
        sa.Column("responsibility_text", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True)),
        sa.Column("removed_by", sa.Uuid()),
        sa.Column("corrected_from", JSONB()),
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
            name="fk_work_log_employee",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "employee_id", "responsibility_id"],
            [
                "employee_responsibilities.company_id",
                "employee_responsibilities.employee_id",
                "employee_responsibilities.id",
            ],
            name="fk_work_log_responsibility",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("from_time <> to_time AND hours>0 AND hours<=24", name="duration"),
        sa.CheckConstraint("(removed_at is null) = (removed_by is null)", name="removed"),
    )
    for column in ("company_id", "employee_id", "date"):
        op.create_index(f"ix_work_log_entries_{column}", "work_log_entries", [column])
    enable_tenant_rls("work_log_entries")
    add_updated_at_trigger("work_log_entries")


def downgrade() -> None:
    op.drop_table("work_log_entries")
    op.drop_constraint(
        "uq_responsibility_company_employee_id", "employee_responsibilities", type_="unique"
    )
