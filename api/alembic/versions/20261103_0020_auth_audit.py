"""Permit private pre-tenant authentication events; no global read permission.

Revision ID: 0020_auth_audit
Revises: 0019_dossier_links
"""

from alembic import op

revision = "0020_auth_audit"
down_revision = "0019_dossier_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE POLICY authentication_audit ON audit_events FOR INSERT TO app_user "
        "WITH CHECK (company_id IS NULL AND actor_type = 'user' AND "
        "((actor_user_id = app_current_user_id() AND action IN "
        "('auth.login.succeeded', 'auth.login.failed', 'auth.logout', 'auth.password.reset', "
        "'auth.step_up.succeeded', 'auth.step_up.failed', 'auth.recovery_codes.regenerated', "
        "'auth.recovery_code.used', 'auth.company.switched', 'auth.mfa.enabled', "
        "'auth.mfa.disabled', 'auth.password.changed')) OR "
        "(actor_user_id IS NULL AND action = 'auth.login.failed')))"
    )


def downgrade() -> None:
    op.execute("DROP POLICY authentication_audit ON audit_events")
