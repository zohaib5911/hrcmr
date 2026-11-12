"""Allow authenticated platform admins to audit register reruns (T20.5)."""

from alembic import op

revision = "0060_register_rerun"
down_revision = "0059_register_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE POLICY platform_register_rerun_audit ON audit_events FOR INSERT TO app_user "
        "WITH CHECK (company_id IS NULL AND actor_type = 'platform_admin' "
        "AND actor_user_id = app_current_user_id() "
        "AND action = 'platform.register_rerun' AND EXISTS "
        "(SELECT 1 FROM platform_admins WHERE user_id = app_current_user_id()))"
    )


def downgrade() -> None:
    op.execute("DROP POLICY platform_register_rerun_audit ON audit_events")
