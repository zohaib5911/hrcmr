"""the company's compliance documents (the 18 a sponsor is expected to hold)

Revision ID: 0008_compliance_documents
Revises: 0007_key_persons
Create Date: 2026-11-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls
from app.modules.companies.reference import COMPLIANCE_DOCUMENT_TYPES, check_sql

revision: str = "0008_compliance_documents"
down_revision: str | None = "0007_key_persons"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "company_compliance_documents"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("doc_type", sa.String(length=40), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
            check_sql("doc_type", COMPLIANCE_DOCUMENT_TYPES),
            name=op.f("ck_company_compliance_documents_doc_type"),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_company_compliance_documents_company_id_companies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["files.id"],
            name=op.f("fk_company_compliance_documents_file_id_files"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_company_compliance_documents")),
    )
    op.create_index(op.f(f"ix_{TABLE}_company_id"), TABLE, ["company_id"], unique=False)
    op.create_index(
        f"uq_{TABLE}_company_id_doc_type",
        TABLE,
        ["company_id", "doc_type"],
        unique=True,
        postgresql_where=sa.text("archived_at is null"),
    )
    add_updated_at_trigger(TABLE)
    enable_tenant_rls(TABLE, privileges=("SELECT", "INSERT", "UPDATE"))


def downgrade() -> None:
    op.drop_table(TABLE)
