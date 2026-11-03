"""Reviewable reminders and owner-only refresh of derived unreported deadlines (T7.4).
Revision ID: 0018_reminders
Revises: 0017_compliance_changes
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision: str = "0018_reminders"
down_revision: str | None = "0017_compliance_changes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen migration values; no imports from live models.
CONDITIONS = {
    "target": "(sponsor_document_id is not null and rtw_check_id is null) or (sponsor_document_id is null and rtw_check_id is not null)",
    "threshold": "threshold_days in (90, 60, 30)",
    "due": "due_on = expires_on - threshold_days",
    "status": "status in ('scheduled', 'due', 'sent', 'snoozed', 'cancelled')",
    "draft": "message_draft is null or (length(trim(message_draft)) > 0 and length(message_draft) <= 2000)",
    "sent": "(status = 'sent' and sent_at is not null and sent_by_user_id is not null and email_outbox_id is not null and message_draft is not null) or (status <> 'sent' and sent_at is null and sent_by_user_id is null and email_outbox_id is null)",
    "snooze": "(status = 'snoozed' and snoozed_until is not null) or (status <> 'snoozed' and snoozed_until is null)",
    "cancelled": "(status = 'cancelled' and cancel_reason is not null and length(trim(cancel_reason)) > 0) or (status <> 'cancelled' and cancel_reason is null)",
}
OLD_CHANGE_TRIGGER = "CREATE OR REPLACE FUNCTION compliance_changes_immutable() RETURNS trigger LANGUAGE plpgsql AS $$\n    BEGIN\n      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Compliance changes are retained'; END IF;\n      IF OLD.reported_at IS NOT NULL OR\n         NEW.id IS DISTINCT FROM OLD.id OR NEW.company_id IS DISTINCT FROM OLD.company_id OR\n         NEW.created_at IS DISTINCT FROM OLD.created_at OR NEW.created_by IS DISTINCT FROM OLD.created_by THEN\n        RAISE EXCEPTION 'Reported compliance changes and record identity are immutable';\n      END IF;\n      IF TG_TABLE_NAME = 'org_changes' THEN\n        IF OLD.archived_at IS NOT NULL THEN RAISE EXCEPTION 'Archived changes are immutable'; END IF;\n      END IF;\n      IF TG_TABLE_NAME = 'change_of_circumstances' OR NEW.reported_at IS NOT NULL THEN\n        IF NEW.reported_at IS NULL OR\n           (to_jsonb(NEW) - ARRAY['reported_at','reported_by_user_id','reported_reference','report_recorded_at','updated_at','updated_by'])\n            IS DISTINCT FROM\n           (to_jsonb(OLD) - ARRAY['reported_at','reported_by_user_id','reported_reference','report_recorded_at','updated_at','updated_by']) THEN\n          RAISE EXCEPTION 'Worker change snapshots are immutable; only record reporting';\n        END IF;\n      END IF;\n      RETURN NEW;\n    END $$"
NEW_CHANGE_TRIGGER = "CREATE OR REPLACE FUNCTION compliance_changes_immutable() RETURNS trigger LANGUAGE plpgsql AS $$\n    BEGIN\n      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Compliance changes are retained'; END IF;\n      -- Only the table owner job may refresh derived dates; entered worker snapshots stay frozen.\n      IF TG_TABLE_NAME = 'change_of_circumstances' AND OLD.reported_at IS NULL AND NEW.reported_at IS NULL\n         AND current_user = pg_catalog.pg_get_userbyid((SELECT relowner FROM pg_catalog.pg_class WHERE oid = TG_RELID))\n         AND (to_jsonb(NEW) - ARRAY['deadline_date','calendar_checked_at','calendar_holidays','updated_at','updated_by'])\n           IS NOT DISTINCT FROM\n             (to_jsonb(OLD) - ARRAY['deadline_date','calendar_checked_at','calendar_holidays','updated_at','updated_by']) THEN\n        RETURN NEW;\n      END IF;\n      IF OLD.reported_at IS NOT NULL OR\n         NEW.id IS DISTINCT FROM OLD.id OR NEW.company_id IS DISTINCT FROM OLD.company_id OR\n         NEW.created_at IS DISTINCT FROM OLD.created_at OR NEW.created_by IS DISTINCT FROM OLD.created_by THEN\n        RAISE EXCEPTION 'Reported compliance changes and record identity are immutable';\n      END IF;\n      IF TG_TABLE_NAME = 'org_changes' THEN\n        IF OLD.archived_at IS NOT NULL THEN RAISE EXCEPTION 'Archived changes are immutable'; END IF;\n      END IF;\n      IF TG_TABLE_NAME = 'change_of_circumstances' OR NEW.reported_at IS NOT NULL THEN\n        IF NEW.reported_at IS NULL OR\n           (to_jsonb(NEW) - ARRAY['reported_at','reported_by_user_id','reported_reference','report_recorded_at','updated_at','updated_by'])\n            IS DISTINCT FROM\n           (to_jsonb(OLD) - ARRAY['reported_at','reported_by_user_id','reported_reference','report_recorded_at','updated_at','updated_by']) THEN\n          RAISE EXCEPTION 'Worker change snapshots are immutable; only record reporting';\n        END IF;\n      END IF;\n      RETURN NEW;\n    END $$"


def upgrade() -> None:
    op.create_table(
        "reminders",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("sponsor_document_id", sa.Uuid()),
        sa.Column("rtw_check_id", sa.Uuid()),
        sa.Column("threshold_days", sa.SmallInteger(), nullable=False),
        sa.Column("expires_on", sa.Date(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(9), server_default="scheduled", nullable=False),
        sa.Column("message_draft", sa.Text()),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("sent_by_user_id", sa.Uuid()),
        sa.Column("email_outbox_id", sa.Uuid()),
        sa.Column("snoozed_until", sa.DateTime(timezone=True)),
        sa.Column("cancel_reason", sa.String(80)),
        sa.Column("admin_notified_at", sa.DateTime(timezone=True)),
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
        sa.ForeignKeyConstraint(
            ["sponsor_document_id"], ["sponsor_documents.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["rtw_check_id"], ["rtw_checks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sent_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["email_outbox_id"], ["email_outbox.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "company_id",
            "sponsor_document_id",
            "threshold_days",
            name="uq_reminders_sponsor_threshold",
        ),
        sa.UniqueConstraint(
            "company_id", "rtw_check_id", "threshold_days", name="uq_reminders_rtw_threshold"
        ),
        *(sa.CheckConstraint(sql, name=name) for name, sql in CONDITIONS.items()),
    )
    op.create_index("ix_reminders_company_id", "reminders", ["company_id"])
    op.create_index("ix_reminders_employee", "reminders", ["company_id", "employee_id"])
    op.create_index("ix_reminders_status_due", "reminders", ["company_id", "status", "due_on"])
    enable_tenant_rls("reminders", privileges=("SELECT", "INSERT", "UPDATE"))
    add_updated_at_trigger("reminders")
    op.execute("""CREATE FUNCTION reminders_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Reminder history is retained'; END IF;
      IF OLD.status = 'sent' OR
         (to_jsonb(NEW) - ARRAY['status','message_draft','sent_at','sent_by_user_id','email_outbox_id','snoozed_until','cancel_reason','admin_notified_at','updated_at','updated_by'])
          IS DISTINCT FROM
         (to_jsonb(OLD) - ARRAY['status','message_draft','sent_at','sent_by_user_id','email_outbox_id','snoozed_until','cancel_reason','admin_notified_at','updated_at','updated_by']) THEN
        RAISE EXCEPTION 'Reminder targets and sent history are immutable';
      END IF;
      RETURN NEW;
    END $$""")
    op.execute(
        "CREATE TRIGGER reminders_immutable BEFORE UPDATE OR DELETE ON reminders FOR EACH ROW EXECUTE FUNCTION reminders_immutable()"
    )
    op.execute(NEW_CHANGE_TRIGGER)


def downgrade() -> None:
    op.execute(OLD_CHANGE_TRIGGER)
    op.drop_table("reminders")
    op.execute("DROP FUNCTION reminders_immutable()")
