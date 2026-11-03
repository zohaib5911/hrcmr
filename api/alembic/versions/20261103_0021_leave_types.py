"""Tenant leave types and frozen GOV.UK-checked defaults (T8.1).
Revision ID: 0021_leave_types
Revises: 0020_auth_audit
"""

from __future__ import annotations

from datetime import date

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision = "0021_leave_types"
down_revision = "0020_auth_audit"
branch_labels = None
depends_on = None

# Frozen migration snapshot: future application reference edits cannot change old migrations.
DEFAULTS = (
    {
        "seed_key": "annual",
        "name": "Annual Leave",
        "is_paid": True,
        "counts_toward_statutory": True,
        "days_per_year": "28.00",
        "carry_over_limit_days": "5.00",
        "colour": "blue",
        "rule_text": "5.6 weeks of paid holiday; 28 days includes bank holidays for a five-day "
        "week. Pro-rate for the working pattern and time employed. Five days is the "
        "company carry-over default; statutory family-leave, sickness and other "
        "protected carry-over can require more.",
        "source_url": "https://www.gov.uk/holiday-entitlement-rights",
    },
    {
        "seed_key": "sick",
        "name": "Sick Leave",
        "is_paid": True,
        "colour": "orange",
        "rule_text": "Eligible employees receive Statutory Sick Pay from the first full day of "
        "sickness absence from 6 April 2026, for up to 28 weeks. Company sick pay may "
        "provide more.",
        "source_url": "https://www.gov.uk/guidance/sickness-absences-that-start-before-and-end-on-or-after-6-april-2026",
    },
    {
        "seed_key": "maternity",
        "name": "Maternity Leave",
        "is_paid": True,
        "colour": "green",
        "rule_text": "Up to 52 weeks of statutory maternity leave. Statutory Maternity Pay lasts "
        "up to 39 weeks where eligible; leave and pay have separate conditions.",
        "source_url": "https://www.gov.uk/maternity-pay-leave",
    },
    {
        "seed_key": "paternity",
        "name": "Paternity Leave",
        "is_paid": True,
        "colour": "green",
        "rule_text": "Up to two weeks, together or as separate one-week blocks, ending within 52 "
        "weeks of birth (or the due date for an early birth). Adoption and Northern "
        "Ireland rules differ. Statutory pay depends on eligibility.",
        "source_url": "https://www.gov.uk/paternity-pay-leave/leave",
    },
    {
        "seed_key": "adoption",
        "name": "Adoption Leave",
        "is_paid": True,
        "colour": "green",
        "rule_text": "Up to 52 weeks of statutory adoption leave for one adopter in a couple. "
        "Statutory Adoption Pay is available subject to eligibility, for up to 39 "
        "weeks.",
        "source_url": "https://www.gov.uk/adoption-pay-leave",
    },
    {
        "seed_key": "shared_parental",
        "name": "Shared Parental Leave",
        "is_paid": True,
        "colour": "green",
        "rule_text": "Eligible parents can share up to 50 weeks of leave and 37 weeks of pay in "
        "the first year after birth or placement. Each parent may book three blocks; "
        "more can be agreed with the employer.",
        "source_url": "https://www.gov.uk/shared-parental-leave-and-pay",
    },
    {
        "seed_key": "neonatal",
        "name": "Neonatal Care Leave",
        "is_paid": True,
        "colour": "green",
        "rule_text": "Eligible employees can take up to 12 weeks of neonatal care leave, within 68 "
        "weeks of birth. One week accrues for each seven continuous full days of "
        "neonatal care. Pay has separate eligibility conditions.",
        "source_url": "https://www.gov.uk/neonatal-care-pay-leave/what-you-get",
    },
    {
        "seed_key": "parental_bereavement",
        "name": "Parental Bereavement Leave",
        "is_paid": True,
        "colour": "red",
        "rule_text": "Eligible employees can take up to two weeks after a child's death or "
        "stillbirth, finishing within 56 weeks. Statutory Parental Bereavement Pay "
        "depends on separate eligibility conditions.",
        "source_url": "https://www.gov.uk/parental-bereavement-pay-leave/what-you-are-entitled-to",
    },
    {
        "seed_key": "parental",
        "name": "Parental Leave",
        "is_paid": False,
        "colour": "gray",
        "rule_text": "Eligible parents can take 18 weeks of unpaid leave per child up to their "
        "18th birthday. Normally no more than four weeks per child each year, in "
        "whole weeks, unless exceptions or an agreement apply.",
        "source_url": "https://www.gov.uk/parental-leave/entitlement",
    },
    {
        "seed_key": "carer",
        "name": "Carer's Leave",
        "is_paid": False,
        "colour": "gray",
        "rule_text": "Up to one normal working week of unpaid carer's leave in each 12 months to "
        "provide or arrange care for a dependant with a long-term care need. "
        "Available from the first day of employment.",
        "source_url": "https://www.gov.uk/carers-leave",
    },
    {
        "seed_key": "dependants",
        "name": "Time Off for Dependants",
        "is_paid": False,
        "colour": "gray",
        "rule_text": "Reasonable time off for an unexpected emergency involving a dependant. There "
        "is no fixed allowance and no requirement to pay; the employment contract may "
        "provide pay.",
        "source_url": "https://www.gov.uk/time-off-for-dependants",
    },
    {
        "seed_key": "unpaid",
        "name": "Unpaid Leave",
        "is_paid": False,
        "colour": "gray",
        "rule_text": "Company policy: unpaid time off by agreement. No automatic annual allowance "
        "is configured. Agree the terms with the employer; statutory leave rights are "
        "separate.",
        "source_url": "https://www.gov.uk/career-breaks",
    },
)


def upgrade() -> None:
    op.create_table(
        "leave_types",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("seed_key", sa.String(24)),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "counts_toward_statutory", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("days_per_year", sa.Numeric(6, 2)),
        sa.Column("carry_over_limit_days", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("accrual_method", sa.String(12), nullable=False, server_default="front_loaded"),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("colour", sa.String(10), nullable=False, server_default="blue"),
        sa.Column("rule_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_url", sa.String(500)),
        sa.Column("checked_on", sa.Date()),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
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
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("company_id", "seed_key", name="uq_leave_types_company_id_seed_key"),
        sa.CheckConstraint("length(trim(name)) > 0", name="name"),
        sa.CheckConstraint("days_per_year IS NULL OR days_per_year >= 0", name="days_per_year"),
        sa.CheckConstraint("carry_over_limit_days >= 0", name="carry_over_limit_days"),
        sa.CheckConstraint("accrual_method in ('front_loaded','monthly')", name="accrual_method"),
        sa.CheckConstraint("colour in ('blue','green','orange','red','gray')", name="colour"),
    )
    op.create_index("ix_leave_types_company_id", "leave_types", ["company_id"])
    op.create_index(
        "uq_leave_types_company_id_name",
        "leave_types",
        ["company_id", sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("archived_at IS NULL"),
    )
    enable_tenant_rls("leave_types")
    add_updated_at_trigger("leave_types")
    seed_table = sa.table(
        "leave_types",
        sa.column("company_id", sa.Uuid()),
        sa.column("seed_key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("is_paid", sa.Boolean()),
        sa.column("counts_toward_statutory", sa.Boolean()),
        sa.column("days_per_year", sa.Numeric()),
        sa.column("carry_over_limit_days", sa.Numeric()),
        sa.column("colour", sa.String()),
        sa.column("rule_text", sa.Text()),
        sa.column("source_url", sa.String()),
        sa.column("checked_on", sa.Date()),
    )
    for company_id in op.get_bind().execute(sa.text("SELECT id FROM companies")).scalars():
        op.bulk_insert(
            seed_table,
            [
                {
                    "counts_toward_statutory": False,
                    "days_per_year": None,
                    "carry_over_limit_days": "0",
                    **values,
                    "company_id": company_id,
                    "checked_on": date(2026, 11, 3),
                }
                for values in DEFAULTS
            ],
        )


def downgrade() -> None:
    op.drop_table("leave_types")
