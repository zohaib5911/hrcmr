"""Versioned employee sponsor documents with masked encrypted references (T7.2).
Revision ID: 0016_sponsor_documents
Revises: 0015_rtw_checks
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision: str = "0016_sponsor_documents"
down_revision: str | None = "0015_rtw_checks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen migration constraints, independent of future model changes.
CONDITIONS = {
    "doc_type": "doc_type in ('visa', 'passport', 'dbs', 'euss', 'national_id', 'other')",
    "version": "version > 0",
    "visa_route": "visa_route is null or visa_route in ('skilled_worker', 'health_care_worker', 'global_business_mobility', 'scale_up', 'temporary_worker', 'graduate', 'student', 'euss_settled', 'euss_pre_settled', 'family', 'other')",
    "visa_fields": "(doc_type = 'visa' and visa_route is not null) or (doc_type <> 'visa' and visa_route is null and cos_number is null and soc_code is null and sponsored_salary is null)",
    "salary": "sponsored_salary is null or sponsored_salary >= 0",
    "soc": "soc_code is null or soc_code ~ '^[0-9]{4}$'",
    "country": "issuing_country is null or issuing_country ~ '^[A-Z]{2}$'",
    "dates": "issue_date is null or expiry_date is null or expiry_date >= issue_date",
    "withdrawal": "(withdrawn_at is null and withdraw_reason is null) or (withdrawn_at is not null and withdraw_reason is not null and length(trim(withdraw_reason)) > 0 and superseded_by is null)",
    "renewal": "renewal_date is not null or renewal_notes is null",
}


def upgrade() -> None:
    op.create_table(
        "sponsor_documents",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("doc_type", sa.String(11), nullable=False),
        sa.Column("reference_number", sa.Text()),
        sa.Column("issuing_country", sa.String(2)),
        sa.Column("visa_route", sa.String(24)),
        sa.Column("cos_number", sa.Text()),
        sa.Column("soc_code", sa.String(4)),
        sa.Column("sponsored_salary", sa.Numeric(12, 2)),
        sa.Column("issue_date", sa.Date()),
        sa.Column("expiry_date", sa.Date()),
        sa.Column("review_date", sa.Date()),
        sa.Column("evidence_file_id", sa.Uuid()),
        sa.Column("remarks", sa.Text()),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("superseded_by", sa.Uuid()),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True)),
        sa.Column("withdraw_reason", sa.Text()),
        sa.Column("renewal_date", sa.Date()),
        sa.Column("renewal_notes", sa.Text()),
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
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evidence_file_id"], ["files.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["superseded_by"],
            ["sponsor_documents.id"],
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.UniqueConstraint("company_id", "employee_id", "doc_type", "version"),
        *(sa.CheckConstraint(sql, name=name) for name, sql in CONDITIONS.items()),
    )
    op.create_index("ix_sponsor_documents_company_id", "sponsor_documents", ["company_id"])
    op.create_index(
        "ix_sponsor_documents_employee", "sponsor_documents", ["company_id", "employee_id"]
    )
    op.create_index(
        "uq_sponsor_documents_current",
        "sponsor_documents",
        ["company_id", "employee_id", "doc_type"],
        unique=True,
        postgresql_where=sa.text("superseded_by is null and withdrawn_at is null"),
    )
    enable_tenant_rls("sponsor_documents", privileges=("SELECT", "INSERT", "UPDATE"))
    add_updated_at_trigger("sponsor_documents")
    op.execute("""CREATE FUNCTION sponsor_documents_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Sponsor documents are retained as evidence'; END IF;
      IF OLD.superseded_by IS NOT NULL OR OLD.withdrawn_at IS NOT NULL OR
         (to_jsonb(NEW) - ARRAY['superseded_by','withdrawn_at','withdraw_reason','renewal_date','renewal_notes','updated_at','updated_by'])
          IS DISTINCT FROM
         (to_jsonb(OLD) - ARRAY['superseded_by','withdrawn_at','withdraw_reason','renewal_date','renewal_notes','updated_at','updated_by']) THEN
        RAISE EXCEPTION 'Sponsor document fields are immutable; record a new version';
      END IF;
      RETURN NEW;
    END $$""")
    op.execute(
        "CREATE TRIGGER sponsor_documents_immutable BEFORE UPDATE OR DELETE ON sponsor_documents FOR EACH ROW EXECUTE FUNCTION sponsor_documents_immutable()"
    )


def downgrade() -> None:
    op.drop_table("sponsor_documents")
    op.execute("DROP FUNCTION sponsor_documents_immutable()")
