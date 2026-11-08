"""Platform company administration (T17.2): platform admins read the metrics, the companies and the
users, and write the company and user actions, each one audited under the platform admin.

``companies`` and ``users`` have no tenant policy (app_user already reads and writes them, see
0002), so the platform code reaches them directly. Three tenant tables need a platform policy to
be read across companies: ``memberships`` (the members of a company and the companies of a user),
``subscriptions`` (refunds in the metrics), and the audit trail for the six company and user
actions, which are written with no company, as 0019, 0035, 0043 and 0048 did.

Revision ID: 0049_platform_company_admin
Revises: 0048_platform_session_audit
"""

from __future__ import annotations

from alembic import op

revision = "0049_platform_company_admin"
down_revision = "0048_platform_session_audit"
branch_labels = None
depends_on = None

PLATFORM_ADMIN = "EXISTS (SELECT 1 FROM platform_admins WHERE user_id = app_current_user_id())"
COMPANY_USER_ACTIONS = (
    "'platform.company_suspended'",
    "'platform.company_reactivated'",
    "'platform.company_plan_extended'",
    "'platform.company_marked_for_deletion'",
    "'platform.user_locked'",
    "'platform.user_unlocked'",
)
ACTIONS = f"({', '.join(COMPANY_USER_ACTIONS)})"


def upgrade() -> None:
    op.execute(
        "CREATE POLICY platform_admin_memberships_read ON memberships AS PERMISSIVE FOR SELECT "
        f"TO app_user USING ({PLATFORM_ADMIN})"
    )
    op.execute(
        "CREATE POLICY platform_admin_subscriptions_read ON subscriptions AS PERMISSIVE FOR SELECT "
        f"TO app_user USING ({PLATFORM_ADMIN})"
    )
    op.execute(
        "CREATE POLICY platform_company_audit ON audit_events FOR INSERT TO app_user "
        "WITH CHECK (company_id IS NULL AND actor_type = 'platform_admin' "
        "AND actor_user_id = app_current_user_id() "
        f"AND action IN {ACTIONS} AND {PLATFORM_ADMIN})"
    )
    op.execute(
        "CREATE POLICY platform_company_audit_read ON audit_events FOR SELECT TO app_user "
        "USING (company_id IS NULL AND actor_type = 'platform_admin' "
        "AND actor_user_id = app_current_user_id() "
        f"AND action IN {ACTIONS} AND {PLATFORM_ADMIN})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY platform_company_audit_read ON audit_events")
    op.execute("DROP POLICY platform_company_audit ON audit_events")
    op.execute("DROP POLICY platform_admin_subscriptions_read ON subscriptions")
    op.execute("DROP POLICY platform_admin_memberships_read ON memberships")
