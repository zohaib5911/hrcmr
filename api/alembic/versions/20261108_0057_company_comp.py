"""Complimentary access (T17.6, owner answer 5): a platform admin gives a company free access for a
number of days, separately from its Stripe plan. ``companies.comp_until`` is that end date: it is
never written by Stripe, so billing history stays true. The grant is audited with no company,
through a named policy, as 0048 to 0056 did.

Revision ID: 0057_company_comp
Revises: 0056_platform_job_rerun
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0057_company_comp"
down_revision = "0056_platform_job_rerun"
branch_labels = None
depends_on = None

PLATFORM_ADMIN = "EXISTS (SELECT 1 FROM platform_admins WHERE user_id = app_current_user_id())"


def upgrade() -> None:
    op.add_column("companies", sa.Column("comp_until", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        "CREATE POLICY platform_company_comp_audit ON audit_events FOR INSERT TO app_user "
        "WITH CHECK (company_id IS NULL AND actor_type = 'platform_admin' "
        "AND actor_user_id = app_current_user_id() "
        f"AND action = 'platform.company_comp_granted' AND {PLATFORM_ADMIN})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY platform_company_comp_audit ON audit_events")
    op.drop_column("companies", "comp_until")
