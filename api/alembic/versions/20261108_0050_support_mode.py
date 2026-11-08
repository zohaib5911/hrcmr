"""Support mode (T17.3): the impersonation sessions table and its audit trail.

``impersonation_sessions`` is a tenant table (the company reads its own rows), and platform admins
read and write it across companies, as the support-mode check runs before any company is chosen.
The company-visible audit events (``support.session.*``) carry the company, so tenant isolation
already admits them. The platform's own record of the same three steps is written with no company,
through a named policy per action, as 0048 and 0049 did.

Revision ID: 0050_support_mode
Revises: 0049_platform_company_admin
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision = "0050_support_mode"
down_revision = "0049_platform_company_admin"
branch_labels = None
depends_on = None

PLATFORM_ADMIN = "EXISTS (SELECT 1 FROM platform_admins WHERE user_id = app_current_user_id())"
SUPPORT_ACTIONS = (
    "'platform.support_started'",
    "'platform.support_writes_changed'",
    "'platform.support_ended'",
)
ACTIONS = f"({', '.join(SUPPORT_ACTIONS)})"


def upgrade() -> None:
    op.create_table(
        "impersonation_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("uuid_generate_v7()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("started_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("ticket_ref", sa.String(80), nullable=False),
        sa.Column("session_id", sa.Uuid()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("write_enabled_at", sa.DateTime(timezone=True)),
        sa.Column("write_enabled_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("ended_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
        sa.CheckConstraint(
            "(write_enabled_at is null) = (write_enabled_by is null)",
            name="write_enabled_state",
        ),
    )
    op.create_index(
        "ix_impersonation_sessions_company_id", "impersonation_sessions", ["company_id"]
    )
    op.create_index(
        "ix_impersonation_sessions_started_by", "impersonation_sessions", ["started_by"]
    )
    enable_tenant_rls("impersonation_sessions", privileges=("SELECT", "INSERT", "UPDATE"))
    add_updated_at_trigger("impersonation_sessions")
    op.execute(
        "CREATE POLICY platform_impersonation_sessions ON impersonation_sessions AS PERMISSIVE "
        f"FOR ALL TO app_user USING ({PLATFORM_ADMIN}) WITH CHECK ({PLATFORM_ADMIN})"
    )
    op.execute(
        "CREATE POLICY platform_support_audit ON audit_events FOR INSERT TO app_user "
        "WITH CHECK (company_id IS NULL AND actor_type = 'platform_admin' "
        "AND actor_user_id = app_current_user_id() "
        f"AND action IN {ACTIONS} AND {PLATFORM_ADMIN})"
    )
    op.execute(
        "CREATE POLICY platform_support_audit_read ON audit_events FOR SELECT TO app_user "
        "USING (company_id IS NULL AND actor_type = 'platform_admin' "
        "AND actor_user_id = app_current_user_id() "
        f"AND action IN {ACTIONS} AND {PLATFORM_ADMIN})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY platform_support_audit_read ON audit_events")
    op.execute("DROP POLICY platform_support_audit ON audit_events")
    op.drop_table("impersonation_sessions")
