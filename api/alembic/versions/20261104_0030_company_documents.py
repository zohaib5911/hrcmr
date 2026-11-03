"""Company document library and review dates (T10.1).

Revision ID: 0030_company_documents
Revises: 0029_work_log
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision = "0030_company_documents"
down_revision = "0029_work_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_documents",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("uuid_generate_v7()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("next_review_date", sa.Date()),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
        sa.ForeignKeyConstraint(
            ["company_id", "file_id"],
            ["files.company_id", "files.id"],
            name="fk_company_documents_file",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "category in ('policy_handbook', 'health_safety', 'companies_house', 'hmrc_payroll', 'insurance', 'premises_lease', 'certificate', 'hr_template', 'training', 'other')",
            name="category",
        ),
        sa.CheckConstraint("length(trim(title)) > 0", name="title"),
    )
    op.create_index("ix_company_documents_company_id", "company_documents", ["company_id"])
    op.create_index(
        "ix_company_documents_review", "company_documents", ["company_id", "next_review_date"]
    )
    enable_tenant_rls("company_documents")
    add_updated_at_trigger("company_documents")


def downgrade() -> None:
    op.drop_table("company_documents")
