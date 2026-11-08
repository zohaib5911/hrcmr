"""Platform session audit (T17.1): platform admins may record their own admin-area access.

The platform session (POST /platform/session) and every page or action through the platform guard
write an audit event with no company. The audit table only accepts such a row through a named
policy per action (see 0019, 0035, 0043), so this adds the same pattern for the three actions the
platform session writes. The insert returns ``created_at``, so the row must also be readable by the
same platform admin, as the other policies do.

Revision ID: 0048_platform_session_audit
Revises: 0047_deletion_requests
"""

from __future__ import annotations

from alembic import op

revision = "0048_platform_session_audit"
down_revision = "0047_deletion_requests"
branch_labels = None
depends_on = None

PLATFORM_SESSION_ACTIONS = (
    "'platform.access'",
    "'platform.session.started'",
    "'platform.session.ended'",
)
ACTIONS = f"({', '.join(PLATFORM_SESSION_ACTIONS)})"
PLATFORM_ADMIN = "EXISTS (SELECT 1 FROM platform_admins WHERE user_id = app_current_user_id())"


def upgrade() -> None:
    op.execute(
        "CREATE POLICY platform_session_audit ON audit_events FOR INSERT TO app_user "
        "WITH CHECK (company_id IS NULL AND actor_type = 'platform_admin' "
        "AND actor_user_id = app_current_user_id() "
        f"AND action IN {ACTIONS} AND {PLATFORM_ADMIN})"
    )
    op.execute(
        "CREATE POLICY platform_session_audit_read ON audit_events FOR SELECT TO app_user "
        "USING (company_id IS NULL AND actor_type = 'platform_admin' "
        "AND actor_user_id = app_current_user_id() "
        f"AND action IN {ACTIONS} AND {PLATFORM_ADMIN})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY platform_session_audit_read ON audit_events")
    op.execute("DROP POLICY platform_session_audit ON audit_events")
