"""Worker/org reporting snapshots and recorded reporting lifecycle (T7.3).
Revision ID: 0017_compliance_changes
Revises: 0016_sponsor_documents
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision: str = "0017_compliance_changes"
down_revision: str | None = "0016_sponsor_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen checks, never imported from live models at migration time.
EMPLOYEE_TYPES_CHECK = "change_type in ('did_not_start', 'unauthorised_absence', 'sponsorship_stopped', 'salary_reduced', 'job_or_soc_changed', 'work_location_changed', 'working_hours_changed', 'unpaid_reduced_absence', 'other')"
ORG_TYPES_CHECK = (
    "change_type in ('address', 'ownership', 'name', 'key_personnel', 'ao_or_key_contact', 'other')"
)
REGION_CHECK = "calendar_region in ('england-and-wales', 'scotland', 'northern-ireland')"
REPORT_CHECK = "(reported_at is null and reported_by_user_id is null and reported_reference is null and report_recorded_at is null) or (reported_at is not null and reported_by_user_id is not null and reported_reference is not null and length(trim(reported_reference)) > 0 and report_recorded_at is not null)"


def _columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("change_date", sa.Date(), nullable=False),
        sa.Column("calendar_region", sa.String(20), nullable=False),
        sa.Column("calendar_checked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "calendar_holidays",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("reported_at", sa.DateTime(timezone=True)),
        sa.Column("reported_by_user_id", sa.Uuid()),
        sa.Column("reported_reference", sa.String(160)),
        sa.Column("report_recorded_at", sa.DateTime(timezone=True)),
        sa.Column("remarks", sa.Text()),
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
    ]


def _constraints() -> list[sa.Constraint]:
    return [
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reported_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(REGION_CHECK, name="region"),
        sa.CheckConstraint(REPORT_CHECK, name="report"),
    ]


def upgrade() -> None:
    op.create_table(
        "change_of_circumstances",
        *_columns(),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("change_type", sa.String(32), nullable=False),
        sa.Column("deadline_date", sa.Date(), nullable=False),
        sa.Column("employment_type", sa.String(12)),
        sa.Column("job_title", sa.String(160)),
        sa.Column("nationality", sa.String(80)),
        sa.Column("contact_number", sa.String(40)),
        sa.Column("address", sa.Text()),
        sa.Column("ack_inform_hr", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "ack_home_office_interview", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column(
            "documents_snapshot",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        *_constraints(),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(EMPLOYEE_TYPES_CHECK, name="change_type"),
        sa.CheckConstraint("deadline_date > change_date", name="deadline"),
        sa.CheckConstraint("calendar_checked_at is not null", name="calendar_checked"),
    )
    op.create_index(
        "ix_change_of_circumstances_employee",
        "change_of_circumstances",
        ["company_id", "employee_id"],
    )
    op.create_table(
        "org_changes",
        *_columns(),
        sa.Column("change_type", sa.String(20), nullable=False),
        sa.Column("deadline_date", sa.Date()),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("archive_reason", sa.Text()),
        *_constraints(),
        sa.CheckConstraint(ORG_TYPES_CHECK, name="change_type"),
        sa.CheckConstraint(
            "(change_type = 'ao_or_key_contact' and deadline_date is null) or (change_type <> 'ao_or_key_contact' and deadline_date is not null and deadline_date > change_date and calendar_checked_at is not null)",
            name="deadline",
        ),
        sa.CheckConstraint(
            "(archived_at is null and archive_reason is null) or (archived_at is not null and archive_reason is not null and length(trim(archive_reason)) > 0 and reported_at is null)",
            name="archive",
        ),
    )
    for table in ("change_of_circumstances", "org_changes"):
        op.create_index(f"ix_{table}_company_id", table, ["company_id"])
        op.create_index(f"ix_{table}_deadline", table, ["company_id", "deadline_date"])
        enable_tenant_rls(table, privileges=("SELECT", "INSERT", "UPDATE"))
        add_updated_at_trigger(table)
    op.execute("""CREATE FUNCTION compliance_changes_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Compliance changes are retained'; END IF;
      IF OLD.reported_at IS NOT NULL OR
         NEW.id IS DISTINCT FROM OLD.id OR NEW.company_id IS DISTINCT FROM OLD.company_id OR
         NEW.created_at IS DISTINCT FROM OLD.created_at OR NEW.created_by IS DISTINCT FROM OLD.created_by THEN
        RAISE EXCEPTION 'Reported compliance changes and record identity are immutable';
      END IF;
      IF TG_TABLE_NAME = 'org_changes' THEN
        IF OLD.archived_at IS NOT NULL THEN RAISE EXCEPTION 'Archived changes are immutable'; END IF;
      END IF;
      IF TG_TABLE_NAME = 'change_of_circumstances' OR NEW.reported_at IS NOT NULL THEN
        IF NEW.reported_at IS NULL OR
           (to_jsonb(NEW) - ARRAY['reported_at','reported_by_user_id','reported_reference','report_recorded_at','updated_at','updated_by'])
            IS DISTINCT FROM
           (to_jsonb(OLD) - ARRAY['reported_at','reported_by_user_id','reported_reference','report_recorded_at','updated_at','updated_by']) THEN
          RAISE EXCEPTION 'Worker change snapshots are immutable; only record reporting';
        END IF;
      END IF;
      RETURN NEW;
    END $$""")
    op.execute(
        "CREATE TRIGGER compliance_changes_immutable BEFORE UPDATE OR DELETE ON change_of_circumstances FOR EACH ROW EXECUTE FUNCTION compliance_changes_immutable()"
    )
    op.execute(
        "CREATE TRIGGER compliance_changes_immutable BEFORE UPDATE OR DELETE ON org_changes FOR EACH ROW EXECUTE FUNCTION compliance_changes_immutable()"
    )


def downgrade() -> None:
    op.drop_table("org_changes")
    op.drop_table("change_of_circumstances")
    op.execute("DROP FUNCTION compliance_changes_immutable()")
