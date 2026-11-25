"""Platform admins approve a held sponsor register import (ISS-11): the app may change only a
publication's status, and record the approval."""

from __future__ import annotations

from alembic import op

revision = "0068_register_hold_review"
down_revision = "0067_security_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT UPDATE (status) ON register_publications TO app_user")
    op.execute(
        "CREATE POLICY platform_register_hold_audit ON audit_events FOR INSERT TO app_user "
        "WITH CHECK (company_id IS NULL AND actor_type = 'platform_admin' "
        "AND actor_user_id = app_current_user_id() "
        "AND action = 'platform.register_hold_approved' AND EXISTS "
        "(SELECT 1 FROM platform_admins WHERE user_id = app_current_user_id()))"
    )


def downgrade() -> None:
    op.execute("DROP POLICY platform_register_hold_audit ON audit_events")
    op.execute("REVOKE UPDATE (status) ON register_publications FROM app_user")
