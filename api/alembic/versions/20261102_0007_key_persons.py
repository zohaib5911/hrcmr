"""key personnel: the Authorising Officer, Key Contact, Level 1 User and Level 2 Users

Revision ID: 0007_key_persons
Revises: 0006_company_structure
Create Date: 2026-11-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision: str = "0007_key_persons"
down_revision: str | None = "0006_company_structure"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "key_persons",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("designation", sa.String(length=120), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("proof_of_id_file_id", sa.Uuid(), nullable=True),
        sa.Column(
            "same_as_authorising_officer", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("is_settled_or_british", sa.Boolean(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "role in ('authorising_officer', 'key_contact', 'level1_user', 'level2_user')",
            name=op.f("ck_key_persons_role"),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_key_persons_company_id_companies"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_key_persons")),
    )
    op.create_index(op.f("ix_key_persons_company_id"), "key_persons", ["company_id"], unique=False)
    op.create_index(
        "uq_key_persons_company_id_role",
        "key_persons",
        ["company_id", "role"],
        unique=True,
        postgresql_where=sa.text("role <> 'level2_user' and archived_at is null"),
    )
    add_updated_at_trigger("key_persons")
    enable_tenant_rls("key_persons", privileges=("SELECT", "INSERT", "UPDATE"))


def downgrade() -> None:
    op.drop_table("key_persons")
