"""Editable global official guidance (T7.5), isolated from tenant permissions.

Revision ID: 0019_dossier_links
Revises: 0018_reminders
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger

revision: str = "0019_dossier_links"
down_revision: str | None = "0018_reminders"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen seed values: publication pages remain useful when the Home Office replaces attachments.
LINKS = (
    (
        "licence",
        "Applying for a sponsor licence",
        "government/publications/workers-and-temporary-workers-guidance-for-sponsors-part-1-apply-for-a-licence",
    ),
    (
        "licence",
        "Sponsor duties and compliance",
        "government/publications/workers-and-temporary-workers-guidance-for-sponsors-part-3-sponsor-duties-and-compliance",
    ),
    (
        "licence",
        "Sponsorship record keeping",
        "government/publications/keep-records-for-sponsorship-appendix-d",
    ),
    ("rtw", "Checking permission to work", "check-job-applicant-right-to-work"),
    (
        "rtw",
        "Employer guidance for Right to Work checks",
        "government/publications/right-to-work-checks-employers-guide",
    ),
    (
        "sms",
        "Managing your sponsor licence (manual 2)",
        "government/publications/manage-your-sponsorship-licence-sms-user-manual",
    ),
    (
        "sms",
        "Reporting worker activity (manual 9)",
        "government/publications/reporting-worker-activity-sms-guide-9",
    ),
    (
        "sms",
        "SMS multi-factor authentication (manual 13)",
        "government/publications/multi-factor-authentication-for-uk-visa-sponsors-sms-manual-13",
    ),
)


def upgrade() -> None:
    op.create_table(
        "dossier_links",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("section", sa.String(10), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("checked_on", sa.Date(), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("section in ('licence', 'rtw', 'sms')", name="section"),
        sa.CheckConstraint("position >= 0", name="position"),
        sa.CheckConstraint("url ~ '^https://www[.]gov[.]uk/[^[:space:]]+$'", name="official_url"),
    )
    add_updated_at_trigger("dossier_links")
    op.execute("ALTER TABLE dossier_links ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY public_reference ON dossier_links FOR SELECT TO app_user USING (true)"
    )
    op.execute(
        "CREATE POLICY platform_content_insert ON dossier_links FOR INSERT TO app_user WITH CHECK (EXISTS (SELECT 1 FROM platform_admins WHERE user_id = app_current_user_id()))"
    )
    op.execute(
        "CREATE POLICY platform_content_update ON dossier_links FOR UPDATE TO app_user USING (EXISTS (SELECT 1 FROM platform_admins WHERE user_id = app_current_user_id())) WITH CHECK (EXISTS (SELECT 1 FROM platform_admins WHERE user_id = app_current_user_id()))"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE ON dossier_links TO app_user")
    # Platform content edits have no company. Tenant events remain confined by the existing policy.
    op.execute(
        "CREATE POLICY platform_content_audit ON audit_events FOR INSERT TO app_user WITH CHECK (company_id IS NULL AND actor_type = 'platform_admin' AND actor_user_id = app_current_user_id() AND action IN ('platform.dossier_link_added', 'platform.dossier_link_updated') AND EXISTS (SELECT 1 FROM platform_admins WHERE user_id = app_current_user_id()))"
    )
    op.execute(
        "CREATE POLICY platform_content_audit_read ON audit_events FOR SELECT TO app_user USING (company_id IS NULL AND actor_type = 'platform_admin' AND actor_user_id = app_current_user_id() AND action IN ('platform.dossier_link_added', 'platform.dossier_link_updated') AND EXISTS (SELECT 1 FROM platform_admins WHERE user_id = app_current_user_id()))"
    )
    table = sa.table(
        "dossier_links",
        *(sa.column(name) for name in ("section", "title", "url", "checked_on", "position")),
    )
    for position, (section, title, path) in enumerate(LINKS):
        op.execute(
            sa.insert(table).values(
                section=section,
                title=title,
                url="https://www.gov.uk/" + path,
                checked_on=date(2026, 11, 3),
                position=position,
            )
        )


def downgrade() -> None:
    op.execute("DROP POLICY platform_content_audit_read ON audit_events")
    op.execute("DROP POLICY platform_content_audit ON audit_events")
    op.drop_table("dossier_links")
