"""the working pattern, bank holidays, holiday types and company holidays

Revision ID: 0009_holidays
Revises: 0008_compliance_documents
Create Date: 2026-11-02
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision: str = "0009_holidays"
down_revision: str | None = "0008_compliance_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLOURS = "('blue', 'green', 'orange', 'red', 'gray')"
REGIONS = "('england-and-wales', 'scotland', 'northern-ireland')"


def _record_columns() -> list[sa.Column[Any]]:
    return [
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
    ]


def _company_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["company_id"],
        ["companies.id"],
        name=op.f(f"fk_{table}_company_id_companies"),
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column(
            "bank_holidays_non_working", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
    )

    op.create_table(
        "working_pattern_days",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("is_working", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("hours", sa.Numeric(4, 2), server_default="0", nullable=False),
        *_record_columns(),
        sa.CheckConstraint("weekday between 1 and 7", name=op.f("ck_working_pattern_days_weekday")),
        sa.CheckConstraint(
            "hours >= 0 and hours <= 24", name=op.f("ck_working_pattern_days_hours")
        ),
        _company_fk("working_pattern_days"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_working_pattern_days")),
        sa.UniqueConstraint(
            "company_id", "weekday", name="uq_working_pattern_days_company_id_weekday"
        ),
    )
    op.create_index(
        op.f("ix_working_pattern_days_company_id"),
        "working_pattern_days",
        ["company_id"],
        unique=False,
    )

    op.create_table(
        "bank_holidays",
        sa.Column("region", sa.String(length=20), nullable=False),
        sa.Column("on_date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        *_record_columns(),
        sa.CheckConstraint(f"region in {REGIONS}", name=op.f("ck_bank_holidays_region")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bank_holidays")),
        sa.UniqueConstraint("region", "on_date", name="uq_bank_holidays_region_on_date"),
    )

    op.create_table(
        "holiday_types",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("colour", sa.String(length=10), server_default="blue", nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *_record_columns(),
        sa.CheckConstraint(f"colour in {COLOURS}", name=op.f("ck_holiday_types_colour")),
        _company_fk("holiday_types"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_holiday_types")),
    )
    op.create_index(
        op.f("ix_holiday_types_company_id"), "holiday_types", ["company_id"], unique=False
    )
    op.create_index(
        "uq_holiday_types_company_id_name",
        "holiday_types",
        ["company_id", sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("archived_at is null"),
    )

    op.create_table(
        "company_holidays",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("holiday_type_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "deduct_from_annual_leave", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *_record_columns(),
        sa.CheckConstraint("end_date >= start_date", name=op.f("ck_company_holidays_dates")),
        _company_fk("company_holidays"),
        sa.ForeignKeyConstraint(
            ["holiday_type_id"],
            ["holiday_types.id"],
            name=op.f("fk_company_holidays_holiday_type_id_holiday_types"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_company_holidays")),
    )
    op.create_index(
        op.f("ix_company_holidays_company_id"), "company_holidays", ["company_id"], unique=False
    )

    for table in ("working_pattern_days", "bank_holidays", "holiday_types", "company_holidays"):
        add_updated_at_trigger(table)
    enable_tenant_rls("working_pattern_days", privileges=("SELECT", "INSERT", "UPDATE"))
    enable_tenant_rls("holiday_types", privileges=("SELECT", "INSERT", "UPDATE"))
    enable_tenant_rls("company_holidays", privileges=("SELECT", "INSERT", "UPDATE"))
    # Public holidays belong to no company: every company reads them; only the weekly import (run
    # as the table owner) writes them.
    op.execute("GRANT SELECT ON bank_holidays TO app_user")


def downgrade() -> None:
    op.drop_table("company_holidays")
    op.drop_table("holiday_types")
    op.drop_table("bank_holidays")
    op.drop_table("working_pattern_days")
    op.drop_column("companies", "bank_holidays_non_working")
