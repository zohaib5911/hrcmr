"""Platform audit log (T17.6): platform admins read the company-less audit trail, and export it.

The trail rows with no company are the platform's own: a platform admin's actions and page views,
and the job runs and failures (actor ``system``). Platform admins read those rows, filtered by
their actor type, through one named policy. Tenant rows (with a company) stay out of reach.
An export is itself recorded, as ``platform.audit_exported``.

Revision ID: 0055_platform_audit_log
Revises: 0054_announcements
"""

from __future__ import annotations

from alembic import op

revision = "0055_platform_audit_log"
down_revision = "0054_announcements"
branch_labels = None
depends_on = None

PLATFORM_ADMIN = "EXISTS (SELECT 1 FROM platform_admins WHERE user_id = app_current_user_id())"


def upgrade() -> None:
    op.execute(
        "CREATE POLICY platform_audit_log_read ON audit_events AS PERMISSIVE FOR SELECT TO app_user "
        "USING (company_id IS NULL AND actor_type IN ('platform_admin', 'system') "
        f"AND {PLATFORM_ADMIN})"
    )
    op.execute(
        "CREATE POLICY platform_audit_export ON audit_events FOR INSERT TO app_user "
        "WITH CHECK (company_id IS NULL AND actor_type = 'platform_admin' "
        "AND actor_user_id = app_current_user_id() "
        f"AND action = 'platform.audit_exported' AND {PLATFORM_ADMIN})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY platform_audit_export ON audit_events")
    op.execute("DROP POLICY platform_audit_log_read ON audit_events")
