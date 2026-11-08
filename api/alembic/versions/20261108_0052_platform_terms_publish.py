"""Terms version publish (T17.5): a platform owner publishes a new version of the terms.

``terms_versions`` is global (no company). ``app_user`` could only read it; publishing needs an
insert, so the grant is added here. The newest ``published_at`` is the current version, and
acceptance is checked per version (rbac/deps.py, rbac/platform.py), so a publish makes everyone
accept again. The publish is written to the audit trail with no company, through a named policy,
as 0048 to 0051 did.

Revision ID: 0052_platform_terms_publish
Revises: 0051_platform_billing_inbox
"""

from __future__ import annotations

from alembic import op

revision = "0052_platform_terms_publish"
down_revision = "0051_platform_billing_inbox"
branch_labels = None
depends_on = None

PLATFORM_ADMIN = "EXISTS (SELECT 1 FROM platform_admins WHERE user_id = app_current_user_id())"
ACTIONS = "('platform.terms_published')"


def upgrade() -> None:
    op.execute("GRANT INSERT ON terms_versions TO app_user")
    op.execute(
        "CREATE POLICY platform_terms_audit ON audit_events FOR INSERT TO app_user "
        "WITH CHECK (company_id IS NULL AND actor_type = 'platform_admin' "
        "AND actor_user_id = app_current_user_id() "
        f"AND action IN {ACTIONS} AND {PLATFORM_ADMIN})"
    )
    op.execute(
        "CREATE POLICY platform_terms_audit_read ON audit_events FOR SELECT TO app_user "
        "USING (company_id IS NULL AND actor_type = 'platform_admin' "
        "AND actor_user_id = app_current_user_id() "
        f"AND action IN {ACTIONS} AND {PLATFORM_ADMIN})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY platform_terms_audit_read ON audit_events")
    op.execute("DROP POLICY platform_terms_audit ON audit_events")
    op.execute("REVOKE INSERT ON terms_versions FROM app_user")
