"""Platform admins publish and roll back the SOC rules versions (plan 8.17, T15.7).

The rules tables are read by every tenant and written only by the table owner (the importers). A
platform admin's publish and rollback run as the app role, so these policies let a platform admin
change the version status and the RQF level of the unit groups, and write the audit event for it.
Everyone else still cannot change a rules row.
"""

from __future__ import annotations

from alembic import op

revision = "0043_rules_platform"
down_revision = "0042_soc_checks"
branch_labels = None
depends_on = None

PLATFORM_ADMIN = "EXISTS (SELECT 1 FROM platform_admins WHERE user_id = app_current_user_id())"
RULES_ACTIONS = "('platform.rules_published', 'platform.rules_rolled_back')"


def upgrade() -> None:
    op.execute(
        "CREATE POLICY platform_rules_update ON rules_versions FOR UPDATE TO app_user "
        f"USING ({PLATFORM_ADMIN}) WITH CHECK ({PLATFORM_ADMIN})"
    )
    op.execute("GRANT UPDATE ON rules_versions TO app_user")
    op.execute(
        "CREATE POLICY platform_soc_unit_rqf ON soc_unit_groups FOR UPDATE TO app_user "
        f"USING ({PLATFORM_ADMIN}) WITH CHECK ({PLATFORM_ADMIN})"
    )
    op.execute("GRANT UPDATE ON soc_unit_groups TO app_user")
    op.execute(
        "CREATE POLICY platform_rules_audit ON audit_events FOR INSERT TO app_user "
        "WITH CHECK (company_id IS NULL AND actor_type = 'platform_admin' "
        "AND actor_user_id = app_current_user_id() "
        f"AND action IN {RULES_ACTIONS} AND {PLATFORM_ADMIN})"
    )
    op.execute(
        "CREATE POLICY platform_rules_audit_read ON audit_events FOR SELECT TO app_user "
        "USING (company_id IS NULL AND actor_type = 'platform_admin' "
        "AND actor_user_id = app_current_user_id() "
        f"AND action IN {RULES_ACTIONS} AND {PLATFORM_ADMIN})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY platform_rules_audit_read ON audit_events")
    op.execute("DROP POLICY platform_rules_audit ON audit_events")
    op.execute("REVOKE UPDATE ON soc_unit_groups FROM app_user")
    op.execute("DROP POLICY platform_soc_unit_rqf ON soc_unit_groups")
    op.execute("REVOKE UPDATE ON rules_versions FROM app_user")
    op.execute("DROP POLICY platform_rules_update ON rules_versions")
