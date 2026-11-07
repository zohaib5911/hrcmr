"""Courses (global super-admin content) and course assignments (plan 6.9)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision = "0035_learning"
down_revision = "0034_organogram"
branch_labels = None
depends_on = None


def _record_columns() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
    ]


def _id() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(
        "id", sa.Uuid(), primary_key=True, server_default=sa.text("uuid_generate_v7()")
    )


def upgrade() -> None:
    op.create_table(
        "courses",
        _id(),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("summary", sa.String(400), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("audience", sa.String(12), nullable=False),
        sa.Column("sections", JSONB(), nullable=False),
        sa.Column("quiz", JSONB(), nullable=False),
        sa.Column("pass_mark", sa.Integer(), nullable=False),
        sa.Column("source_title", sa.String(200), nullable=False),
        sa.Column("source_publisher", sa.String(120), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("source_updated_on", sa.Date(), nullable=False),
        sa.Column("content_reviewed_on", sa.Date(), nullable=False),
        sa.Column("licence_note", sa.String(400)),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        *_record_columns(),
        sa.CheckConstraint("audience in ('all_staff', 'managers')", name="audience"),
        sa.CheckConstraint("duration_minutes between 5 and 120", name="duration_minutes"),
        sa.CheckConstraint("pass_mark between 1 and 100", name="pass_mark"),
        sa.CheckConstraint("source_url like 'https://%'", name="source_url"),
        sa.CheckConstraint("version >= 1", name="version"),
    )
    add_updated_at_trigger("courses")
    # Courses are shared by every company, so only published ones are readable by a tenant; the
    # platform's editors (platform_admins) see and change every course, as on dossier_links.
    op.execute("ALTER TABLE courses ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY course_read ON courses FOR SELECT TO app_user "
        "USING (published OR EXISTS (SELECT 1 FROM platform_admins "
        "WHERE user_id = app_current_user_id()))"
    )
    op.execute(
        "CREATE POLICY platform_course_insert ON courses FOR INSERT TO app_user "
        "WITH CHECK (EXISTS (SELECT 1 FROM platform_admins WHERE user_id = app_current_user_id()))"
    )
    op.execute(
        "CREATE POLICY platform_course_update ON courses FOR UPDATE TO app_user "
        "USING (EXISTS (SELECT 1 FROM platform_admins WHERE user_id = app_current_user_id())) "
        "WITH CHECK (EXISTS (SELECT 1 FROM platform_admins WHERE user_id = app_current_user_id()))"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE ON courses TO app_user")
    # The insert returns created_at, so the new row must also be readable by the same platform admin.
    op.execute(
        "CREATE POLICY platform_course_audit ON audit_events FOR INSERT TO app_user "
        "WITH CHECK (company_id IS NULL AND actor_type = 'platform_admin' "
        "AND actor_user_id = app_current_user_id() "
        "AND action IN ('platform.course_created', 'platform.course_updated') "
        "AND EXISTS (SELECT 1 FROM platform_admins WHERE user_id = app_current_user_id()))"
    )
    op.execute(
        "CREATE POLICY platform_course_audit_read ON audit_events FOR SELECT TO app_user "
        "USING (company_id IS NULL AND actor_type = 'platform_admin' "
        "AND actor_user_id = app_current_user_id() "
        "AND action IN ('platform.course_created', 'platform.course_updated') "
        "AND EXISTS (SELECT 1 FROM platform_admins WHERE user_id = app_current_user_id()))"
    )

    op.create_table(
        "course_assignments",
        _id(),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "course_id", sa.Uuid(), sa.ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "employee_id",
            sa.Uuid(),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="not_started"),
        sa.Column("progress", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("quiz_score", sa.Integer()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("assigned_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        *_record_columns(),
        sa.UniqueConstraint(
            "company_id", "course_id", "employee_id", name="uq_course_assignments_one_per_person"
        ),
        sa.CheckConstraint(
            "status in ('not_started', 'in_progress', 'completed', 'overdue')", name="status"
        ),
        sa.CheckConstraint("quiz_score is null or quiz_score between 0 and 100", name="quiz_score"),
    )
    enable_tenant_rls("course_assignments")
    add_updated_at_trigger("course_assignments")


def downgrade() -> None:
    op.drop_table("course_assignments")
    op.execute("DROP POLICY platform_course_audit_read ON audit_events")
    op.execute("DROP POLICY platform_course_audit ON audit_events")
    op.drop_table("courses")
