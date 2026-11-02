"""pay settings: bank accounts (encrypted), tax codes, payment types, pay bands, pay schedules

Revision ID: 0011_pay_settings
Revises: 0010_trading_hours
Create Date: 2026-11-02
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision: str = "0011_pay_settings"
down_revision: str | None = "0010_trading_hours"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("company_bank_accounts", "tax_codes", "payment_types", "pay_bands", "pay_schedules")


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


def _archived() -> sa.Column[Any]:
    return sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True)


def _company_index(table: str) -> None:
    op.create_index(op.f(f"ix_{table}_company_id"), table, ["company_id"], unique=False)


def _unique_name(table: str, name: str) -> None:
    op.create_index(
        f"uq_{table}_company_id_{name}",
        table,
        ["company_id", sa.text(f"lower({name})")],
        unique=True,
        postgresql_where=sa.text("archived_at is null"),
    )


def upgrade() -> None:
    op.create_table(
        "company_bank_accounts",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("bank_name", sa.String(length=120), nullable=False),
        sa.Column("account_holder", sa.String(length=120), nullable=False),
        sa.Column("sort_code", sa.Text(), nullable=False),
        sa.Column("account_number", sa.Text(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False),
        _archived(),
        *_record_columns(),
        _company_fk("company_bank_accounts"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_company_bank_accounts")),
    )

    op.create_table(
        "tax_codes",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=12), nullable=False),
        sa.Column("reference", sa.String(length=80), nullable=True),
        sa.Column("deduction_percentage", sa.Numeric(5, 2), nullable=False),
        _archived(),
        *_record_columns(),
        sa.CheckConstraint(
            "deduction_percentage between 0 and 100",
            name=op.f("ck_tax_codes_deduction_percentage"),
        ),
        _company_fk("tax_codes"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tax_codes")),
    )
    _unique_name("tax_codes", "code")

    op.create_table(
        "payment_types",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("min_hourly_rate", sa.Numeric(8, 2), nullable=False),
        _archived(),
        *_record_columns(),
        sa.CheckConstraint("min_hourly_rate >= 0", name=op.f("ck_payment_types_min_hourly_rate")),
        _company_fk("payment_types"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_types")),
    )
    _unique_name("payment_types", "name")

    op.create_table(
        "pay_bands",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("min_annual", sa.Numeric(12, 2), nullable=False),
        sa.Column("max_annual", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="GBP", nullable=False),
        _archived(),
        *_record_columns(),
        sa.CheckConstraint(
            "min_annual >= 0 and max_annual >= min_annual", name=op.f("ck_pay_bands_range")
        ),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name=op.f("ck_pay_bands_currency")),
        _company_fk("pay_bands"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pay_bands")),
    )
    _unique_name("pay_bands", "name")

    op.create_table(
        "pay_schedules",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("frequency", sa.String(length=12), nullable=False),
        sa.Column("pay_day_kind", sa.String(length=20), nullable=False),
        sa.Column("pay_day_value", sa.SmallInteger(), nullable=True),
        _archived(),
        *_record_columns(),
        sa.CheckConstraint(
            "frequency in ('weekly', 'fortnightly', 'four_weekly', 'monthly')",
            name=op.f("ck_pay_schedules_frequency"),
        ),
        sa.CheckConstraint(
            "pay_day_kind in ('weekday', 'day_of_month', 'last_day', 'last_working_day')",
            name=op.f("ck_pay_schedules_pay_day_kind"),
        ),
        sa.CheckConstraint(
            "(pay_day_kind = 'weekday' and pay_day_value between 1 and 7)"
            " or (pay_day_kind = 'day_of_month' and pay_day_value between 1 and 28)"
            " or (pay_day_kind in ('last_day', 'last_working_day') and pay_day_value is null)",
            name=op.f("ck_pay_schedules_pay_day"),
        ),
        _company_fk("pay_schedules"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pay_schedules")),
    )
    _unique_name("pay_schedules", "name")

    for table in TABLES:
        _company_index(table)
        add_updated_at_trigger(table)
        enable_tenant_rls(table, privileges=("SELECT", "INSERT", "UPDATE"))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
