"""identity core

Revision ID: 0002_identity_core
Revises: 0001_foundations
Create Date: 2026-11-02 02:35:48.682268
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls
from app.db.roles import APP_ROLE

revision: str = "0002_identity_core"
down_revision: str | None = "0001_foundations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every table below carries `updated_at` except the append-only audit trail.
UPDATED_AT_TABLES = (
    "companies",
    "users",
    "memberships",
    "platform_admins",
    "sessions",
    "invitations",
    "email_tokens",
    "terms_versions",
    "terms_acceptances",
    "files",
    "notifications",
)

# What the API's role (app_user) may do to tables that have no tenant policy (they are read before
# a company is known, or are not about a company at all). The owner, used by migrations, can do
# everything. Written out in full, one statement each, so each can be read and checked on its own.
GRANTS = (
    "GRANT SELECT, INSERT, UPDATE ON companies TO app_user",
    "GRANT SELECT, INSERT, UPDATE ON users TO app_user",
    "GRANT SELECT ON platform_admins TO app_user",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON sessions TO app_user",
    "GRANT SELECT, INSERT, UPDATE ON invitations TO app_user",
    "GRANT SELECT, INSERT, UPDATE ON email_tokens TO app_user",
    "GRANT SELECT ON terms_versions TO app_user",
    "GRANT SELECT, INSERT ON terms_acceptances TO app_user",
)
if APP_ROLE != "app_user":  # the statements above name the role literally
    raise RuntimeError("the grants in this migration name app_user, which is no longer APP_ROLE")

# The signed-in person, set per transaction next to `app.company_id`. Unset gives NULL, which
# matches nothing, so a connection that does not say who it is sees no memberships.
CURRENT_USER_FUNCTION = """
CREATE FUNCTION app_current_user_id() RETURNS uuid
LANGUAGE sql STABLE PARALLEL SAFE
AS $$ SELECT NULLIF(current_setting('app.user_id', true), '')::uuid $$
"""

APPEND_ONLY_FUNCTION = """
CREATE FUNCTION audit_events_append_only() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only: % is not allowed', TG_OP
        USING ERRCODE = 'integrity_constraint_violation';
END
$$
"""


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=60), nullable=True),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.String(length=400), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("impersonation_session_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.CheckConstraint(
            "actor_type in ('user', 'platform_admin', 'system')",
            name=op.f("ck_audit_events_actor_type"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(
        "ix_audit_events_company_id_created_at",
        "audit_events",
        ["company_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_audit_events_entity", "audit_events", ["entity_type", "entity_id"], unique=False
    )
    op.create_table(
        "companies",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("trading_name", sa.String(length=200), nullable=True),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("registered_number", sa.String(length=20), nullable=True),
        sa.Column("type_of_organisation", sa.String(length=60), nullable=True),
        sa.Column("trading_period", sa.String(length=40), nullable=True),
        sa.Column("sector", sa.String(length=10), nullable=True),
        sa.Column("size_band", sa.String(length=20), nullable=True),
        sa.Column("contact_email", sa.String(length=254), nullable=True),
        sa.Column("contact_phone", sa.String(length=40), nullable=True),
        sa.Column("website", sa.String(length=300), nullable=True),
        sa.Column("logo_file_id", sa.Uuid(), nullable=True),
        sa.Column("country", sa.String(length=2), server_default="GB", nullable=False),
        sa.Column("region", sa.String(length=2), server_default="uk", nullable=False),
        sa.Column(
            "bank_holiday_region",
            sa.String(length=20),
            server_default="england-and-wales",
            nullable=False,
        ),
        sa.Column("timezone", sa.String(length=64), server_default="Europe/London", nullable=False),
        sa.Column("default_currency", sa.String(length=3), server_default="GBP", nullable=False),
        sa.Column("week_starts_on", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column(
            "leave_year_start_month_day",
            sa.String(length=5),
            server_default="01-01",
            nullable=False,
        ),
        sa.Column(
            "allow_negative_leave_balance",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("mfa_policy", sa.String(length=10), server_default="optional", nullable=False),
        sa.Column(
            "changed_name_last_5_years",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("previous_company_name", sa.String(length=200), nullable=True),
        sa.Column(
            "penalty_illegal_working_last_3_years",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("penalty_illegal_working_status", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("plan", sa.String(length=10), server_default="free", nullable=False),
        sa.Column("subscription_status", sa.String(length=30), nullable=True),
        sa.Column("subscription_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("subscription_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cooling_off_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stripe_customer_id", sa.String(length=80), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(length=80), nullable=True),
        sa.Column("setup_checklist_dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "bank_holiday_region in ('england-and-wales', 'scotland', 'northern-ireland')",
            name=op.f("ck_companies_bank_holiday_region"),
        ),
        sa.CheckConstraint(
            "leave_year_start_month_day ~ '^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'",
            name=op.f("ck_companies_leave_year_start_month_day"),
        ),
        sa.CheckConstraint(
            "mfa_policy in ('optional', 'admins', 'all')", name=op.f("ck_companies_mfa_policy")
        ),
        sa.CheckConstraint(
            "plan in ('free', 'annual', 'ten_year')", name=op.f("ck_companies_plan")
        ),
        sa.CheckConstraint("region in ('uk', 'us', 'au')", name=op.f("ck_companies_region")),
        sa.CheckConstraint(
            "status in ('active', 'suspended', 'pending_deletion', 'deleted')",
            name=op.f("ck_companies_status"),
        ),
        sa.CheckConstraint(
            "week_starts_on between 1 and 7", name=op.f("ck_companies_week_starts_on")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_companies")),
        sa.UniqueConstraint("slug", name=op.f("uq_companies_slug")),
        sa.UniqueConstraint("stripe_customer_id", name=op.f("uq_companies_stripe_customer_id")),
        sa.UniqueConstraint(
            "stripe_subscription_id", name=op.f("uq_companies_stripe_subscription_id")
        ),
    )
    op.create_table(
        "terms_versions",
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("url", sa.String(length=300), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_terms_versions")),
        sa.UniqueConstraint("version", name=op.f("uq_terms_versions_version")),
    )
    op.create_table(
        "users",
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("mfa_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("mfa_secret", sa.Text(), nullable=True),
        sa.Column(
            "recovery_codes_hash",
            sa.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "requires_password_change",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("theme_pref", sa.String(length=10), server_default="system", nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "theme_pref in ('system', 'light', 'dark')", name=op.f("ck_users_theme_pref")
        ),
        sa.CheckConstraint("failed_login_count >= 0", name=op.f("ck_users_failed_login_count")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "email_tokens",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "purpose in ('verify', 'reset', 'deletion_code', 'login_alert')",
            name=op.f("ck_email_tokens_purpose"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_email_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_email_tokens_token_hash")),
    )
    op.create_index(op.f("ix_email_tokens_user_id"), "email_tokens", ["user_id"], unique=False)
    op.create_table(
        "files",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(length=300), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("mime", sa.String(length=100), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("scan_status", sa.String(length=10), server_default="pending", nullable=False),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_type", sa.String(length=40), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("category", sa.String(length=40), nullable=True),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "scan_status in ('pending', 'clean', 'infected', 'error')",
            name=op.f("ck_files_scan_status"),
        ),
        sa.CheckConstraint("size >= 0", name=op.f("ck_files_size")),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_files_company_id_companies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["users.id"],
            name=op.f("fk_files_uploaded_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_files")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_files_storage_key")),
    )
    op.create_index(op.f("ix_files_company_id"), "files", ["company_id"], unique=False)
    op.create_index("ix_files_owner", "files", ["owner_type", "owner_id"], unique=False)
    op.create_table(
        "invitations",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invited_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "role in ('company_admin', 'hr_admin', 'people_manager', 'recruiter', 'employee', 'read_only_auditor')",
            name=op.f("ck_invitations_role"),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_invitations_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by"],
            ["users.id"],
            name=op.f("fk_invitations_invited_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invitations")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_invitations_token_hash")),
    )
    op.create_index(op.f("ix_invitations_company_id"), "invitations", ["company_id"], unique=False)
    op.create_table(
        "memberships",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=10), server_default="active", nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "role in ('company_admin', 'hr_admin', 'people_manager', 'recruiter', 'employee', 'read_only_auditor')",
            name=op.f("ck_memberships_role"),
        ),
        sa.CheckConstraint("status in ('active', 'suspended')", name=op.f("ck_memberships_status")),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_memberships_company_id_companies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_memberships_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memberships")),
        sa.UniqueConstraint("user_id", "company_id", name="uq_memberships_user_id_company_id"),
    )
    op.create_index(op.f("ix_memberships_company_id"), "memberships", ["company_id"], unique=False)
    op.create_index(op.f("ix_memberships_user_id"), "memberships", ["user_id"], unique=False)
    op.create_index(
        "uq_memberships_company_id_employee_id",
        "memberships",
        ["company_id", "employee_id"],
        unique=True,
        postgresql_where=sa.text("employee_id is not null"),
    )
    op.create_table(
        "notifications",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("link", sa.String(length=300), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_notifications_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notifications_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index(
        op.f("ix_notifications_company_id"), "notifications", ["company_id"], unique=False
    )
    op.create_index(
        "ix_notifications_user_id_read_at", "notifications", ["user_id", "read_at"], unique=False
    )
    op.create_table(
        "platform_admins",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("level", sa.String(length=10), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint("level in ('support', 'owner')", name=op.f("ck_platform_admins_level")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_platform_admins_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform_admins")),
        sa.UniqueConstraint("user_id", name=op.f("uq_platform_admins_user_id")),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.String(length=400), nullable=True),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mfa_passed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("step_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_sessions_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sessions_token_hash")),
    )
    op.create_index(op.f("ix_sessions_company_id"), "sessions", ["company_id"], unique=False)
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)
    op.create_table(
        "terms_acceptances",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_terms_acceptances_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["version"],
            ["terms_versions.version"],
            name=op.f("fk_terms_acceptances_version_terms_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_terms_acceptances")),
        sa.UniqueConstraint("user_id", "version", name="uq_terms_acceptances_user_id_version"),
    )
    op.create_index(
        op.f("ix_terms_acceptances_user_id"), "terms_acceptances", ["user_id"], unique=False
    )

    for table in UPDATED_AT_TABLES:
        add_updated_at_trigger(table)

    # Tenant tables: a company sees only its own rows. A person can also read their own memberships,
    # which is how sign-in finds the companies to offer.
    op.execute(CURRENT_USER_FUNCTION)
    enable_tenant_rls("memberships", privileges=("SELECT", "INSERT", "UPDATE"))
    op.execute(
        f"CREATE POLICY own_memberships ON memberships AS PERMISSIVE FOR SELECT TO {APP_ROLE} "
        "USING (user_id = app_current_user_id())"
    )
    enable_tenant_rls("files", privileges=("SELECT", "INSERT", "UPDATE"))
    enable_tenant_rls("notifications")

    # The audit trail: the API may add and read, never change or remove (and a trigger enforces the
    # same for every role, the owner included).
    enable_tenant_rls("audit_events", privileges=("SELECT", "INSERT"))
    op.execute(APPEND_ONLY_FUNCTION)
    op.execute(
        "CREATE TRIGGER trg_audit_events_append_only BEFORE UPDATE OR DELETE ON audit_events "
        "FOR EACH ROW EXECUTE FUNCTION audit_events_append_only()"
    )
    op.execute(
        "CREATE TRIGGER trg_audit_events_no_truncate BEFORE TRUNCATE ON audit_events "
        "FOR EACH STATEMENT EXECUTE FUNCTION audit_events_append_only()"
    )

    for grant in GRANTS:
        op.execute(grant)


def downgrade() -> None:
    op.drop_index(op.f("ix_terms_acceptances_user_id"), table_name="terms_acceptances")
    op.drop_table("terms_acceptances")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_company_id"), table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("platform_admins")
    op.drop_index("ix_notifications_user_id_read_at", table_name="notifications")
    op.drop_index(op.f("ix_notifications_company_id"), table_name="notifications")
    op.drop_table("notifications")
    op.drop_index(
        "uq_memberships_company_id_employee_id",
        table_name="memberships",
        postgresql_where=sa.text("employee_id is not null"),
    )
    op.drop_index(op.f("ix_memberships_user_id"), table_name="memberships")
    op.drop_index(op.f("ix_memberships_company_id"), table_name="memberships")
    op.drop_table("memberships")
    op.drop_index(op.f("ix_invitations_company_id"), table_name="invitations")
    op.drop_table("invitations")
    op.drop_index("ix_files_owner", table_name="files")
    op.drop_index(op.f("ix_files_company_id"), table_name="files")
    op.drop_table("files")
    op.drop_index(op.f("ix_email_tokens_user_id"), table_name="email_tokens")
    op.drop_table("email_tokens")
    op.drop_table("users")
    op.drop_table("terms_versions")
    op.drop_table("companies")
    op.drop_index("ix_audit_events_entity", table_name="audit_events")
    op.drop_index("ix_audit_events_company_id_created_at", table_name="audit_events")
    op.drop_table("audit_events")
    op.execute("DROP FUNCTION IF EXISTS audit_events_append_only()")
    op.execute("DROP FUNCTION IF EXISTS app_current_user_id()")
