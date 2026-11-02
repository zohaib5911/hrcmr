"""employees (plan 6.3): the record, addresses, emergency contacts, bank details, assignments,
responsibilities, compensation, previous employment, education, training, memberships, documents

Revision ID: 0013_employees
Revises: 0012_invitation_names
Create Date: 2026-11-02
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision: str = "0013_employees"
down_revision: str | None = "0012_invitation_names"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUSES = ("active", "on_leave", "leaver", "archived")
RELATIONSHIPS = (
    "spouse",
    "partner",
    "parent",
    "child",
    "sibling",
    "relative",
    "friend",
    "other",
)
EMPLOYMENT_TYPES = (
    "full_time",
    "part_time",
    "fixed_term",
    "zero_hours",
    "casual",
    "apprentice",
    "agency",
)
FREQUENCIES = ("annual", "monthly", "hourly")
DOCUMENT_CATEGORIES = (
    "employment_contract",
    "letter",
    "hr_record",
    "id_document",
    "rtw_evidence",
    "certificate",
    "payslip",
    "other",
)

CHILD_TABLES = (
    "employee_addresses",
    "emergency_contacts",
    "employee_bank_details",
    "employee_assignments",
    "employee_responsibilities",
    "employee_compensation",
    "employee_previous_employment",
    "employee_education",
    "employee_training_records",
    "employee_memberships",
    "employee_documents",
)
TABLES = ("employees", *CHILD_TABLES)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} in ({', '.join(repr(v) for v in values)})"


def _record_columns() -> list[sa.Column[Any]]:
    now = sa.text("now()")
    return [
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
    ]


def _table(name: str, *items: sa.SchemaItem, child: bool = True) -> None:
    columns: list[sa.SchemaItem] = [sa.Column("company_id", sa.Uuid(), nullable=False)]
    if child:
        columns.append(sa.Column("employee_id", sa.Uuid(), nullable=False))
    op.create_table(
        name,
        *columns,
        *items,
        *_record_columns(),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f(f"fk_{name}_company_id_companies"),
            ondelete="RESTRICT",
        ),
        *(
            [
                sa.ForeignKeyConstraint(
                    ["employee_id"],
                    ["employees.id"],
                    name=op.f(f"fk_{name}_employee_id_employees"),
                    ondelete="CASCADE",
                )
            ]
            if child
            else []
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{name}")),
    )
    op.create_index(op.f(f"ix_{name}_company_id"), name, ["company_id"], unique=False)
    if child:
        op.create_index(op.f(f"ix_{name}_employee_id"), name, ["employee_id"], unique=False)


def _fk(
    name: str, column: str, target: str, *, ondelete: str = "SET NULL"
) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [target], name=op.f(f"fk_{name}_{column}"), ondelete=ondelete
    )


def _str(name: str, length: int, *, null: bool = True) -> sa.Column[Any]:
    return sa.Column(name, sa.String(length=length), nullable=null)


def upgrade() -> None:
    _table(
        "employees",
        _str("employee_number", 50, null=False),
        _str("first_name", 100, null=False),
        _str("last_name", 100, null=False),
        _str("email", 254, null=False),
        _str("phone", 40),
        _str("alt_phone", 40),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        _str("gender", 30),
        _str("marital_status", 30),
        _str("nationality", 80),
        sa.Column("photo_file_id", sa.Uuid(), nullable=True),
        sa.Column("hire_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=10), server_default="active", nullable=False),
        sa.Column("leave_date", sa.Date(), nullable=True),
        sa.Column("opted_out_48h_week", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("ni_number", sa.Text(), nullable=True),
        sa.Column("ni_number_index", sa.String(length=64), nullable=True),
        sa.Column("passport_number", sa.Text(), nullable=True),
        _str("passport_country", 80),
        sa.Column("passport_expiry", sa.Date(), nullable=True),
        _fk("employees", "photo_file_id", "files.id"),
        sa.CheckConstraint(_in("status", STATUSES), name=op.f("ck_employees_status")),
        child=False,
    )
    op.create_index(
        "uq_employees_company_id_employee_number",
        "employees",
        ["company_id", sa.text("lower(regexp_replace(employee_number, '\\s', '', 'g'))")],
        unique=True,
    )
    op.create_index("ix_employees_company_id_status", "employees", ["company_id", "status"])
    op.create_index(
        "ix_employees_company_id_ni_number_index",
        "employees",
        ["company_id", "ni_number_index"],
        postgresql_where=sa.text("ni_number_index is not null"),
    )

    _table(
        "employee_addresses",
        _str("postcode", 12),
        _str("line1", 120, null=False),
        _str("line2", 120),
        _str("line3", 120),
        _str("city_county", 120),
        _str("country", 80),
        sa.Column("is_current", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    _table(
        "emergency_contacts",
        _str("name", 120, null=False),
        sa.Column("relationship", sa.String(length=20), nullable=False),
        _str("phone", 40, null=False),
        _str("email", 254),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.CheckConstraint(
            _in("relationship", RELATIONSHIPS), name=op.f("ck_emergency_contacts_relationship")
        ),
    )
    _table(
        "employee_bank_details",
        _str("account_holder", 120, null=False),
        _str("bank_name", 120, null=False),
        sa.Column("sort_code", sa.Text(), nullable=False),
        sa.Column("account_number", sa.Text(), nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.create_index(
        "uq_employee_bank_details_employee_id_current",
        "employee_bank_details",
        ["employee_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )
    _table(
        "employee_assignments",
        sa.Column("department_id", sa.Uuid(), nullable=True),
        sa.Column("designation_id", sa.Uuid(), nullable=True),
        sa.Column("location_id", sa.Uuid(), nullable=True),
        sa.Column("reporting_authority_employee_id", sa.Uuid(), nullable=True),
        sa.Column("leave_sanctioning_employee_id", sa.Uuid(), nullable=True),
        sa.Column("organogram_level_id", sa.Uuid(), nullable=True),
        sa.Column("employment_type", sa.String(length=12), nullable=False),
        sa.Column("custom_working_days", postgresql.JSONB(), nullable=True),
        sa.Column("hours_per_day", sa.Numeric(4, 2), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("ended_at", sa.Date(), nullable=True),
        _fk("employee_assignments", "department_id", "departments.id"),
        _fk("employee_assignments", "designation_id", "designations.id"),
        _fk("employee_assignments", "location_id", "locations.id"),
        _fk(
            "employee_assignments",
            "reporting_authority_employee_id",
            "employees.id",
        ),
        _fk("employee_assignments", "leave_sanctioning_employee_id", "employees.id"),
        sa.CheckConstraint(
            _in("employment_type", EMPLOYMENT_TYPES),
            name=op.f("ck_employee_assignments_employment_type"),
        ),
    )
    op.create_index(
        "uq_employee_assignments_employee_id_current",
        "employee_assignments",
        ["employee_id"],
        unique=True,
        postgresql_where=sa.text("ended_at is null"),
    )
    op.create_index(
        "ix_employee_assignments_reporting",
        "employee_assignments",
        ["reporting_authority_employee_id"],
        postgresql_where=sa.text("ended_at is null"),
    )
    op.create_index(
        "ix_employee_assignments_leave",
        "employee_assignments",
        ["leave_sanctioning_employee_id"],
        postgresql_where=sa.text("ended_at is null"),
    )
    _table(
        "employee_responsibilities",
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sort", sa.Integer(), server_default="0", nullable=False),
    )
    _table(
        "employee_compensation",
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("frequency", sa.String(length=10), nullable=False),
        sa.Column("contracted_hours_per_week", sa.Numeric(5, 2), nullable=True),
        sa.Column("tax_code_id", sa.Uuid(), nullable=True),
        sa.Column("payment_type_id", sa.Uuid(), nullable=True),
        sa.Column("pay_band_id", sa.Uuid(), nullable=True),
        sa.Column("pay_schedule_id", sa.Uuid(), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        _fk("employee_compensation", "tax_code_id", "tax_codes.id"),
        _fk("employee_compensation", "payment_type_id", "payment_types.id"),
        _fk("employee_compensation", "pay_band_id", "pay_bands.id"),
        _fk("employee_compensation", "pay_schedule_id", "pay_schedules.id"),
        sa.CheckConstraint(
            _in("frequency", FREQUENCIES), name=op.f("ck_employee_compensation_frequency")
        ),
        sa.CheckConstraint("amount >= 0", name=op.f("ck_employee_compensation_amount")),
    )
    _table(
        "employee_previous_employment",
        _str("job_title", 120),
        sa.Column("started_on", sa.Date(), nullable=True),
        sa.Column("left_on", sa.Date(), nullable=True),
        sa.Column("total_experience_years", sa.Numeric(4, 1), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_index(
        "uq_employee_previous_employment_employee_id",
        "employee_previous_employment",
        ["employee_id"],
        unique=True,
    )
    _table(
        "employee_education",
        _str("qualification", 120, null=False),
        _str("subject", 120),
        _str("institution", 120),
        _str("awarding_body", 120),
        sa.Column("year", sa.SmallInteger(), nullable=True),
        sa.Column("percentage", sa.Numeric(5, 2), nullable=True),
        _str("grade", 40),
    )
    _table(
        "employee_training_records",
        _str("title", 160, null=False),
        sa.Column("started_on", sa.Date(), nullable=True),
        sa.Column("ended_on", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
    )
    _table(
        "employee_memberships",
        _str("licence_title", 160, null=False),
        _str("licence_number", 80),
        sa.Column("started_on", sa.Date(), nullable=True),
        sa.Column("ended_on", sa.Date(), nullable=True),
    )
    _table(
        "employee_documents",
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=24), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        _fk("employee_documents", "file_id", "files.id", ondelete="RESTRICT"),
        sa.CheckConstraint(
            _in("category", DOCUMENT_CATEGORIES), name=op.f("ck_employee_documents_category")
        ),
    )

    for table in TABLES:
        add_updated_at_trigger(table)
        enable_tenant_rls(table, privileges=("SELECT", "INSERT", "UPDATE", "DELETE"))
    # The membership's link to an employee record can now be a real foreign key.
    op.create_foreign_key(
        op.f("fk_memberships_employee_id_employees"),
        "memberships",
        "employees",
        ["employee_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_memberships_employee_id_employees"), "memberships", type_="foreignkey"
    )
    for table in reversed(TABLES):
        op.drop_table(table)
