"""Versioned policies and immutable employee sign-off evidence (T10.3).

Revision ID: 0032_policy_signoffs
Revises: 0031_report_jobs
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision = "0032_policy_signoffs"
down_revision = "0031_report_jobs"
branch_labels = None
depends_on = None


def _record_columns() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
    ]


def upgrade() -> None:
    op.create_table(
        "policy_documents",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("uuid_generate_v7()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("previous_version_id", sa.Uuid()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("file_id", sa.Uuid()),
        sa.Column("confirmation_mode", sa.String(6), nullable=False, server_default="accept"),
        sa.Column("audience_type", sa.String(12), nullable=False, server_default="everyone"),
        sa.Column("audience_ids", ARRAY(sa.Uuid()), nullable=False, server_default="{}"),
        sa.Column("accept_within_days", sa.Integer(), nullable=False, server_default="14"),
        sa.Column(
            "auto_send_new_starters", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("status", sa.String(8), nullable=False, server_default="draft"),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("sent_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        *_record_columns(),
        sa.UniqueConstraint("company_id", "id", name="uq_policy_documents_company_id_id"),
        sa.UniqueConstraint(
            "company_id", "group_id", "version", name="uq_policy_documents_group_version"
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "file_id"],
            ["files.company_id", "files.id"],
            name="fk_policy_documents_file",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "group_id"],
            ["policy_documents.company_id", "policy_documents.id"],
            name="fk_policy_documents_group",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "previous_version_id"],
            ["policy_documents.company_id", "policy_documents.id"],
            name="fk_policy_documents_previous",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "category in ('employment_contract', 'job_description', 'offer_letter', 'contract_change', 'company_policy', 'employee_handbook', 'code_of_conduct', 'it_email_social_media', 'drugs_alcohol', 'sickness_sick_pay', 'attendance_punctuality', 'holiday_annual_leave', 'flexible_hybrid_working', 'family_leave', 'equality_diversity', 'anti_harassment', 'grievance', 'disciplinary', 'whistleblowing', 'health_safety', 'privacy_notice', 'sponsor_duties', 'other')",
            name="category",
        ),
        sa.CheckConstraint("length(trim(title)) > 0", name="title"),
        sa.CheckConstraint("confirmation_mode in ('accept','sign')", name="confirmation_mode"),
        sa.CheckConstraint(
            "audience_type in ('everyone','departments','locations','named','visa_holders')",
            name="audience_type",
        ),
        sa.CheckConstraint(
            "cardinality(audience_ids) <= 500 and ((audience_type in ('departments','locations','named')) = (cardinality(audience_ids) > 0))",
            name="audience_selection",
        ),
        sa.CheckConstraint("status in ('draft','sent','archived')", name="status"),
        sa.CheckConstraint("accept_within_days between 1 and 365", name="accept_within_days"),
        sa.CheckConstraint(
            "version > 0 and ((version=1) = (previous_version_id is null))", name="version"
        ),
        sa.CheckConstraint(
            "status <> 'sent' or (file_id is not null and sent_at is not null and sent_by is not null)",
            name="sent_state",
        ),
    )
    op.create_index("ix_policy_documents_company_id", "policy_documents", ["company_id"])
    for state in ("draft", "sent"):
        op.create_index(
            f"uq_policy_documents_live_{state}",
            "policy_documents",
            ["company_id", "group_id"],
            unique=True,
            postgresql_where=sa.text(f"status = '{state}'"),
        )
    enable_tenant_rls("policy_documents")
    add_updated_at_trigger("policy_documents")
    op.create_table(
        "policy_acceptances",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("uuid_generate_v7()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("policy_document_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(8), nullable=False, server_default="pending"),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("accepted_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("typed_signature", sa.Text()),
        sa.Column("ip", sa.String(45)),
        sa.Column("user_agent", sa.String(500)),
        sa.Column("last_reminded_at", sa.DateTime(timezone=True)),
        *_record_columns(),
        sa.UniqueConstraint(
            "company_id", "policy_document_id", "employee_id", name="uq_policy_acceptances_employee"
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "policy_document_id"],
            ["policy_documents.company_id", "policy_documents.id"],
            name="fk_policy_acceptances_document",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "employee_id"],
            ["employees.company_id", "employees.id"],
            name="fk_policy_acceptances_employee",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("status in ('pending','accepted','signed','overdue')", name="status"),
        sa.CheckConstraint(
            "(status in ('accepted','signed')) = (accepted_at is not null)", name="accepted_state"
        ),
        sa.CheckConstraint(
            "(status in ('accepted','signed')) = (accepted_by is not null)", name="actor_state"
        ),
        sa.CheckConstraint(
            "(status = 'signed') = (typed_signature is not null)", name="signature_state"
        ),
        sa.CheckConstraint(
            "accepted_at is not null or (ip is null and user_agent is null)",
            name="pending_evidence",
        ),
    )
    for column in ("company_id", "policy_document_id", "employee_id"):
        op.create_index(f"ix_policy_acceptances_{column}", "policy_acceptances", [column])
    op.create_index(
        "ix_policy_acceptances_due", "policy_acceptances", ["company_id", "status", "due_on"]
    )
    enable_tenant_rls("policy_acceptances")
    add_updated_at_trigger("policy_acceptances")
    op.execute("""CREATE FUNCTION policy_documents_frozen() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Policy history cannot be deleted' USING ERRCODE = '23514';
      END IF;
      IF OLD.status = 'draft' THEN RETURN NEW; END IF;
      IF OLD.status = 'sent' AND NEW.status = 'archived'
         AND (to_jsonb(NEW) - ARRAY['status','archived_at','updated_at','updated_by']) =
             (to_jsonb(OLD) - ARRAY['status','archived_at','updated_at','updated_by'])
         AND NEW.archived_at IS NOT NULL THEN RETURN NEW; END IF;
      RAISE EXCEPTION 'Sent policy versions are immutable' USING ERRCODE = '23514';
    END; $$""")
    op.execute("""CREATE TRIGGER trg_policy_documents_frozen BEFORE UPDATE OR DELETE ON policy_documents
    FOR EACH ROW EXECUTE FUNCTION policy_documents_frozen()""")
    op.execute("""CREATE FUNCTION policy_acceptances_frozen() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE mode text; policy_state text;
    BEGIN
      IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Policy receipts cannot be deleted' USING ERRCODE = '23514';
      END IF;
      IF TG_OP = 'UPDATE' THEN
        IF OLD.accepted_at IS NOT NULL THEN
          RAISE EXCEPTION 'Completed policy receipts are immutable' USING ERRCODE = '23514';
        END IF;
        IF (NEW.company_id,NEW.policy_document_id,NEW.employee_id,NEW.due_on,NEW.created_at)
           IS DISTINCT FROM
           (OLD.company_id,OLD.policy_document_id,OLD.employee_id,OLD.due_on,OLD.created_at) THEN
          RAISE EXCEPTION 'Policy assignments retain their original recipient and deadline' USING ERRCODE = '23514';
        END IF;
      END IF;
      IF NEW.status IN ('accepted','signed') THEN
        SELECT confirmation_mode,status INTO mode,policy_state FROM policy_documents
          WHERE id=NEW.policy_document_id AND company_id=NEW.company_id;
        IF policy_state IS DISTINCT FROM 'sent' OR
           (mode='sign' AND NEW.status <> 'signed') OR
           (mode='accept' AND NEW.status <> 'accepted') THEN
          RAISE EXCEPTION 'Policy confirmation must match its sent version' USING ERRCODE = '23514';
        END IF;
      END IF;
      RETURN NEW;
    END; $$""")
    op.execute("""CREATE TRIGGER trg_policy_acceptances_frozen BEFORE INSERT OR UPDATE OR DELETE ON policy_acceptances
    FOR EACH ROW EXECUTE FUNCTION policy_acceptances_frozen()""")


def downgrade() -> None:
    op.drop_table("policy_acceptances")
    op.drop_table("policy_documents")
    op.execute("DROP FUNCTION policy_acceptances_frozen()")
    op.execute("DROP FUNCTION policy_documents_frozen()")
