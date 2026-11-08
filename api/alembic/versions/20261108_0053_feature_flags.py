"""Feature flags (T17.5): a platform admin turns a named feature on or off for everyone.

``feature_flags`` is global (no company). The key is a short lower-case name, checked by the
database as well as the API. The app reads it on any session (``SELECT``); only platform code
writes it (``INSERT`` and ``UPDATE``), and each change is audited with no company, through a named
policy, as 0048 to 0052 did.

Revision ID: 0053_feature_flags
Revises: 0052_platform_terms_publish
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger

revision = "0053_feature_flags"
down_revision = "0052_platform_terms_publish"
branch_labels = None
depends_on = None

PLATFORM_ADMIN = "EXISTS (SELECT 1 FROM platform_admins WHERE user_id = app_current_user_id())"
ACTIONS = "('platform.feature_flag_changed')"


def upgrade() -> None:
    op.create_table(
        "feature_flags",
        sa.Column("key", sa.String(60), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("description", sa.String(300), nullable=False, server_default=""),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.CheckConstraint("key ~ '^[a-z][a-z0-9_]{2,59}$'", name="key_format"),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_feature_flags")),
    )
    add_updated_at_trigger("feature_flags")
    op.execute("GRANT SELECT, INSERT, UPDATE ON feature_flags TO app_user")
    op.execute(
        "CREATE POLICY platform_flags_audit ON audit_events FOR INSERT TO app_user "
        "WITH CHECK (company_id IS NULL AND actor_type = 'platform_admin' "
        "AND actor_user_id = app_current_user_id() "
        f"AND action IN {ACTIONS} AND {PLATFORM_ADMIN})"
    )
    op.execute(
        "CREATE POLICY platform_flags_audit_read ON audit_events FOR SELECT TO app_user "
        "USING (company_id IS NULL AND actor_type = 'platform_admin' "
        "AND actor_user_id = app_current_user_id() "
        f"AND action IN {ACTIONS} AND {PLATFORM_ADMIN})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY platform_flags_audit_read ON audit_events")
    op.execute("DROP POLICY platform_flags_audit ON audit_events")
    op.drop_table("feature_flags")
