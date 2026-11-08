"""Announcement banner (T17.5): a message shown to every company in a region, for a set period.

``announcements`` is global (no company): a platform admin schedules it for a region, and each
company reads the live ones for its own region. A platform admin can end one early; the row is
kept. The app reads and writes it (``SELECT``, ``INSERT``, ``UPDATE``), and each change is audited
with no company, through a named policy, as 0048 to 0053 did.

Revision ID: 0054_announcements
Revises: 0053_feature_flags
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0054_announcements"
down_revision = "0053_feature_flags"
branch_labels = None
depends_on = None

PLATFORM_ADMIN = "EXISTS (SELECT 1 FROM platform_admins WHERE user_id = app_current_user_id())"
ACTIONS = "('platform.announcement_created', 'platform.announcement_ended')"
REGIONS = ("uk", "us", "au")


def upgrade() -> None:
    op.create_table(
        "announcements",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("region", sa.String(2), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("body", sa.String(500), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_announcements")),
        sa.CheckConstraint(
            "region in (" + ", ".join(f"'{r}'" for r in REGIONS) + ")", name="region"
        ),
        sa.CheckConstraint("ends_at > starts_at", name="period"),
    )
    op.create_index("ix_announcements_region_period", "announcements", ["region", "ends_at"])
    op.execute("GRANT SELECT, INSERT, UPDATE ON announcements TO app_user")
    op.execute(
        "CREATE POLICY platform_announcements_audit ON audit_events FOR INSERT TO app_user "
        "WITH CHECK (company_id IS NULL AND actor_type = 'platform_admin' "
        "AND actor_user_id = app_current_user_id() "
        f"AND action IN {ACTIONS} AND {PLATFORM_ADMIN})"
    )
    op.execute(
        "CREATE POLICY platform_announcements_audit_read ON audit_events FOR SELECT TO app_user "
        "USING (company_id IS NULL AND actor_type = 'platform_admin' "
        "AND actor_user_id = app_current_user_id() "
        f"AND action IN {ACTIONS} AND {PLATFORM_ADMIN})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY platform_announcements_audit_read ON audit_events")
    op.execute("DROP POLICY platform_announcements_audit ON audit_events")
    op.drop_index("ix_announcements_region_period", table_name="announcements")
    op.drop_table("announcements")
