"""Versioned RTW checks and a caller-scoped derived-status view (T7.1).
Revision ID: 0015_rtw_checks
Revises: 0014_emergency_relationships
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger, create_tenant_view, enable_tenant_rls

revision: str = "0015_rtw_checks"
down_revision: str | None = "0014_emergency_relationships"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONDITIONS = {
    "subject_type": "subject_type in ('employee', 'candidate')",
    "check_type": "check_type in ('online_share_code', 'idsp_digital', 'manual_list_a', 'manual_list_b')",
    "outcome": "outcome in ('pending', 'verified', 'failed')",
    "employee_checker": "subject_type <> 'employee' or (check_date is not null and checked_by_user_id is not null)",
    "permission_expiry": "(permission_expires and permission_expires_on is not null) or (not permission_expires and permission_expires_on is null)",
    "online_code": "(check_type = 'online_share_code' and share_code is not null) or (check_type <> 'online_share_code' and share_code is null)",
    "idsp": "(check_type = 'idsp_digital' and idsp_provider is not null and idsp_document is not null and idsp_document in ('british_passport', 'irish_passport', 'irish_passport_card')) or (check_type <> 'idsp_digital' and idsp_provider is null and idsp_document is null)",
    "list_b": "(check_type = 'manual_list_b' and list_b_group is not null and list_b_group in ('group1', 'group2') and permission_expires) or (check_type <> 'manual_list_b' and list_b_group is null)",
    "indefinite": "check_type not in ('idsp_digital', 'manual_list_a') or not permission_expires",
    "correction": "(corrected_from_id is null and correction_reason is null) or (corrected_from_id is not null and correction_reason is not null and length(trim(correction_reason)) > 0)",
    "superseded": "(superseded_at is null and superseded_by is null) or superseded_at is not null",
}
FOLLOW_UP = "CASE WHEN permission_expires THEN permission_expires_on ELSE NULL END"


def upgrade() -> None:
    op.create_table(
        "rtw_checks",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("subject_type", sa.String(9), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("check_type", sa.String(24), nullable=False),
        sa.Column("share_code", sa.Text()),
        sa.Column("idsp_provider", sa.String(160)),
        sa.Column("idsp_document", sa.String(24)),
        sa.Column("list_b_group", sa.String(6)),
        sa.Column("permission_expires", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("permission_expires_on", sa.Date()),
        sa.Column("follow_up_due_on", sa.Date(), sa.Computed(FOLLOW_UP, persisted=True)),
        sa.Column("check_date", sa.Date()),
        sa.Column("checked_by_user_id", sa.Uuid()),
        sa.Column("outcome", sa.String(8), nullable=False),
        sa.Column("evidence_file_id", sa.Uuid()),
        sa.Column("superseded_at", sa.DateTime(timezone=True)),
        sa.Column("superseded_by", sa.Uuid()),
        sa.Column("corrected_from_id", sa.Uuid(), unique=True),
        sa.Column("correction_reason", sa.Text()),
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
        sa.ForeignKeyConstraint(["checked_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evidence_file_id"], ["files.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["superseded_by"],
            ["rtw_checks.id"],
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(["corrected_from_id"], ["rtw_checks.id"], ondelete="RESTRICT"),
        *(sa.CheckConstraint(sql, name=name) for name, sql in CONDITIONS.items()),
    )
    op.create_index("ix_rtw_checks_company_id", "rtw_checks", ["company_id"])
    op.create_index(
        "ix_rtw_checks_subject", "rtw_checks", ["company_id", "subject_type", "subject_id"]
    )
    op.create_index(
        "uq_rtw_checks_current",
        "rtw_checks",
        ["company_id", "subject_type", "subject_id"],
        unique=True,
        postgresql_where=sa.text("superseded_at is null"),
    )
    enable_tenant_rls("rtw_checks", privileges=("SELECT", "INSERT", "UPDATE"))
    add_updated_at_trigger("rtw_checks")
    op.execute("""CREATE FUNCTION rtw_checks_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'RTW checks are retained as evidence'; END IF;
      IF OLD.superseded_at IS NOT NULL OR
         (to_jsonb(NEW) - ARRAY['superseded_at','superseded_by','updated_at','updated_by','follow_up_due_on'])
          IS DISTINCT FROM
         (to_jsonb(OLD) - ARRAY['superseded_at','superseded_by','updated_at','updated_by','follow_up_due_on']) OR
         NEW.superseded_at IS NULL OR NEW.superseded_by IS NULL THEN
        RAISE EXCEPTION 'RTW check fields are immutable; record a correction';
      END IF;
      RETURN NEW;
    END $$""")
    op.execute(
        "CREATE TRIGGER rtw_checks_immutable BEFORE UPDATE OR DELETE ON rtw_checks FOR EACH ROW EXECUTE FUNCTION rtw_checks_immutable()"
    )
    create_tenant_view(
        "employee_rtw_status",
        """
      SELECT e.id AS employee_id, e.company_id, c.id AS current_check_id, c.follow_up_due_on,
        CASE WHEN c.id IS NULL THEN 'not_recorded'
             WHEN c.outcome = 'failed' THEN 'failed'
             WHEN c.outcome = 'pending' THEN 'pending'
             WHEN c.follow_up_due_on < (CURRENT_TIMESTAMP AT TIME ZONE co.timezone)::date THEN 'expired'
             WHEN f.id IS NULL OR f.scan_status <> 'clean' THEN 'evidence_missing'
             WHEN c.follow_up_due_on <= (CURRENT_TIMESTAMP AT TIME ZONE co.timezone)::date + 60 THEN 'expiring'
             ELSE 'verified' END AS status
      FROM employees e JOIN companies co ON co.id=e.company_id
      LEFT JOIN rtw_checks c ON c.company_id=e.company_id AND c.subject_type='employee'
        AND c.subject_id=e.id AND c.superseded_at IS NULL
      LEFT JOIN files f ON f.id=c.evidence_file_id AND f.company_id=e.company_id
    """,
    )


def downgrade() -> None:
    op.execute("DROP VIEW employee_rtw_status")
    op.drop_table("rtw_checks")
    op.execute("DROP FUNCTION rtw_checks_immutable()")
