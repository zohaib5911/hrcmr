"""Tenant shift types, late policies and day off patterns (T9.4).

Revision ID: 0027_rota_settings
Revises: 0026_attendance_clock
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision = "0027_rota_settings"
down_revision = "0026_attendance_clock"
branch_labels = None
depends_on = None


def _columns() -> list[sa.Column]:  # type: ignore[type-arg]
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
        sa.Column("archived_at", sa.DateTime(timezone=True)),
    ]


def _scopes(table: str) -> list[sa.ForeignKeyConstraint]:
    return [
        sa.ForeignKeyConstraint(
            ["company_id", "department_id"],
            ["departments.company_id", "departments.id"],
            name=f"fk_{table}_department",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "department_id", "designation_id"],
            ["designations.company_id", "designations.department_id", "designations.id"],
            name=f"fk_{table}_designation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "shift_type_id"],
            ["shift_types.company_id", "shift_types.id"],
            name=f"fk_{table}_shift",
            ondelete="RESTRICT",
        ),
    ]


def upgrade() -> None:
    op.create_unique_constraint("uq_departments_company_id_id", "departments", ["company_id", "id"])
    op.create_unique_constraint(
        "uq_designations_company_department_id",
        "designations",
        ["company_id", "department_id", "id"],
    )
    op.create_table(
        "shift_types",
        *_columns(),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("starts_at", sa.Time(), nullable=False),
        sa.Column("ends_at", sa.Time(), nullable=False),
        sa.Column("break_start", sa.Time()),
        sa.Column("break_end", sa.Time()),
        sa.Column("colour", sa.String(7), nullable=False, server_default="#007aff"),
        sa.UniqueConstraint("company_id", "id", name="uq_shift_types_company_id_id"),
        sa.CheckConstraint("starts_at <> ends_at", name="duration"),
        sa.CheckConstraint("(break_start is null) = (break_end is null)", name="break_pair"),
    )
    op.create_index(
        "uq_shift_types_live_name",
        "shift_types",
        ["company_id", sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("archived_at is null"),
    )
    op.create_table(
        "late_policies",
        *_columns(),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("designation_id", sa.Uuid(), nullable=False),
        sa.Column("shift_type_id", sa.Uuid(), nullable=False),
        sa.Column("grace_minutes", sa.Integer(), nullable=False),
        sa.Column("allowed_late_days_per_month", sa.Integer(), nullable=False),
        sa.Column("deduction_type", sa.String(20), nullable=False),
        sa.Column("deduction_value", sa.Numeric(10, 2), nullable=False),
        *_scopes("late_policies"),
        sa.CheckConstraint(
            "grace_minutes between 0 and 1440 AND allowed_late_days_per_month between 0 and 31",
            name="limits",
        ),
        sa.CheckConstraint(
            "deduction_value >= 0 AND ((deduction_type='none' AND deduction_value=0) OR deduction_type='fixed' OR (deduction_type='percentage_of_day' AND deduction_value<=100))",
            name="deduction",
        ),
    )
    op.create_table(
        "day_off_patterns",
        *_columns(),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("designation_id", sa.Uuid(), nullable=False),
        sa.Column("shift_type_id", sa.Uuid(), nullable=False),
        sa.Column("weekdays_off", ARRAY(sa.Integer()), nullable=False),
        sa.Column("works_public_holidays", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_scopes("day_off_patterns"),
        sa.CheckConstraint(
            "weekdays_off <@ ARRAY[1,2,3,4,5,6,7] AND array_position(weekdays_off, NULL) IS NULL",
            name="weekdays",
        ),
    )
    for table in ("shift_types", "late_policies", "day_off_patterns"):
        op.create_index(f"ix_{table}_company_id", table, ["company_id"])
        if table != "shift_types":
            op.create_index(
                f"uq_{table}_live_scope",
                table,
                ["company_id", "department_id", "designation_id", "shift_type_id"],
                unique=True,
                postgresql_where=sa.text("archived_at is null"),
            )
        enable_tenant_rls(table)
        add_updated_at_trigger(table)


def downgrade() -> None:
    for table in ("day_off_patterns", "late_policies", "shift_types"):
        op.drop_table(table)
    op.drop_constraint("uq_designations_company_department_id", "designations", type_="unique")
    op.drop_constraint("uq_departments_company_id_id", "departments", type_="unique")
