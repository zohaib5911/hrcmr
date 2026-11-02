"""locations, departments and designations

Revision ID: 0006_company_structure
Revises: 0005_company_details
Create Date: 2026-11-02
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision: str = "0006_company_structure"
down_revision: str | None = "0005_company_details"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("postcode", sa.String(length=10), nullable=False),
        sa.Column("address_line1", sa.String(length=120), nullable=False),
        sa.Column("address_line2", sa.String(length=120), nullable=True),
        sa.Column("address_line3", sa.String(length=120), nullable=True),
        sa.Column("city", sa.String(length=80), nullable=False),
        sa.Column("county", sa.String(length=80), nullable=True),
        sa.Column("country", sa.String(length=60), server_default="United Kingdom", nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *_record_columns(),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_locations_company_id_companies"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_locations")),
    )
    op.create_index(op.f("ix_locations_company_id"), "locations", ["company_id"], unique=False)
    op.create_index(
        "uq_locations_company_id_default",
        "locations",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text("is_default and archived_at is null"),
    )

    op.create_table(
        "departments",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *_record_columns(),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_departments_company_id_companies"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_departments")),
    )
    op.create_index(op.f("ix_departments_company_id"), "departments", ["company_id"], unique=False)
    op.create_index(
        "uq_departments_company_id_name",
        "departments",
        ["company_id", sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("archived_at is null"),
    )

    op.create_table(
        "designations",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("soc_code", sa.String(length=4), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *_record_columns(),
        sa.CheckConstraint(r"soc_code ~ '^[0-9]{4}$'", name=op.f("ck_designations_soc_code")),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_designations_company_id_companies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name=op.f("fk_designations_department_id_departments"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_designations")),
    )
    op.create_index(
        op.f("ix_designations_company_id"), "designations", ["company_id"], unique=False
    )
    op.create_index(
        op.f("ix_designations_department_id"), "designations", ["department_id"], unique=False
    )
    op.create_index(
        "uq_designations_department_id_title",
        "designations",
        ["department_id", sa.text("lower(title)")],
        unique=True,
        postgresql_where=sa.text("archived_at is null"),
    )

    for table in ("locations", "departments", "designations"):
        add_updated_at_trigger(table)
        # Rows are archived, never deleted, so the API's role has no DELETE.
        enable_tenant_rls(table, privileges=("SELECT", "INSERT", "UPDATE"))


def downgrade() -> None:
    op.drop_table("designations")
    op.drop_table("departments")
    op.drop_table("locations")
