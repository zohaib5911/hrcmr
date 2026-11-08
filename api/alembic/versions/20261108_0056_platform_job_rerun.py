"""Re-running a failed job (T17.6): the re-run is written to the audit trail with no company, through
a named policy, as 0048 to 0055 did. Only the allow-listed jobs can be re-run (app/jobs/rerun.py).

Revision ID: 0056_platform_job_rerun
Revises: 0055_platform_audit_log
"""

from __future__ import annotations

from alembic import op

revision = "0056_platform_job_rerun"
down_revision = "0055_platform_audit_log"
branch_labels = None
depends_on = None

PLATFORM_ADMIN = "EXISTS (SELECT 1 FROM platform_admins WHERE user_id = app_current_user_id())"


def upgrade() -> None:
    op.execute(
        "CREATE POLICY platform_job_rerun_audit ON audit_events FOR INSERT TO app_user "
        "WITH CHECK (company_id IS NULL AND actor_type = 'platform_admin' "
        "AND actor_user_id = app_current_user_id() "
        f"AND action = 'platform.job_rerun' AND {PLATFORM_ADMIN})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY platform_job_rerun_audit ON audit_events")
