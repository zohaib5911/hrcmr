"""Requisitions, postings, candidates, applications, interviews and offers (plan 6.8)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision = "0033_recruitment"
down_revision = "0032_policy_signoffs"
branch_labels = None
depends_on = None

TABLES = (
    "requisitions",
    "postings",
    "candidates",
    "applications",
    "interviews",
    "offers",
)


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


def _company() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(
        "company_id",
        sa.Uuid(),
        sa.ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )


def _id() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(
        "id", sa.Uuid(), primary_key=True, server_default=sa.text("uuid_generate_v7()")
    )


def upgrade() -> None:
    op.create_table(
        "requisitions",
        _id(),
        _company(),
        sa.Column("job_title", sa.String(200), nullable=False),
        sa.Column("department_id", sa.Uuid(), sa.ForeignKey("departments.id", ondelete="RESTRICT")),
        sa.Column("headcount", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("grade", sa.String(40)),
        sa.Column("budget_from", sa.Numeric(12, 2)),
        sa.Column("budget_to", sa.Numeric(12, 2)),
        sa.Column("budget_per", sa.String(6)),
        sa.Column("justification", sa.Text()),
        sa.Column("status", sa.String(10), nullable=False, server_default="draft"),
        sa.Column("approved_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        *_record_columns(),
        sa.UniqueConstraint("company_id", "id", name="uq_requisitions_company_id_id"),
        sa.CheckConstraint("length(trim(job_title)) > 0", name="job_title"),
        sa.CheckConstraint("headcount between 1 and 999", name="headcount"),
        sa.CheckConstraint(
            "status in ('draft','open','on_hold','filled','cancelled')", name="status"
        ),
        sa.CheckConstraint(
            "budget_per is null or budget_per in ('year','month','hour')", name="budget_per"
        ),
        sa.CheckConstraint(
            "budget_from is null or budget_to is null or budget_from <= budget_to",
            name="budget_range",
        ),
        sa.CheckConstraint("(approved_by is null) = (approved_at is null)", name="approval_stamp"),
        sa.CheckConstraint(
            "status not in ('open','filled') or approved_at is not null",
            name="approved_before_open",
        ),
    )
    op.create_table(
        "postings",
        _id(),
        _company(),
        sa.Column(
            "requisition_id",
            sa.Uuid(),
            sa.ForeignKey("requisitions.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("visibility", sa.String(8), nullable=False, server_default="internal"),
        sa.Column("location_id", sa.Uuid(), sa.ForeignKey("locations.id", ondelete="RESTRICT")),
        sa.Column("job_code", sa.String(40)),
        sa.Column("soc_code", sa.String(10)),
        sa.Column("vacancies", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("posted_on", sa.Date()),
        sa.Column("closes_on", sa.Date()),
        sa.Column("contact_email", sa.String(254)),
        sa.Column("contact_phone", sa.String(40)),
        sa.Column("salary_from", sa.Numeric(12, 2)),
        sa.Column("salary_to", sa.Numeric(12, 2)),
        sa.Column("salary_per", sa.String(6)),
        sa.Column("weekly_hours", sa.Numeric(4, 1)),
        sa.Column("description", sa.Text()),
        sa.Column("visa_sponsorship", sa.String(14), nullable=False, server_default="not_stated"),
        sa.Column("status", sa.String(6), nullable=False, server_default="draft"),
        *_record_columns(),
        sa.UniqueConstraint("company_id", "id", name="uq_postings_company_id_id"),
        sa.UniqueConstraint("company_id", "slug", name="uq_postings_slug"),
        sa.CheckConstraint("length(trim(title)) > 0", name="title"),
        sa.CheckConstraint("visibility in ('internal','external')", name="visibility"),
        sa.CheckConstraint("vacancies between 1 and 999", name="vacancies"),
        sa.CheckConstraint("status in ('draft','open','closed')", name="status"),
        sa.CheckConstraint(
            "visa_sponsorship in ('not_stated','available','considered','not_available')",
            name="visa_sponsorship",
        ),
        sa.CheckConstraint(
            "salary_per is null or salary_per in ('year','month','hour')", name="salary_per"
        ),
        sa.CheckConstraint(
            "salary_from is null or salary_to is null or salary_from <= salary_to",
            name="salary_range",
        ),
    )
    op.create_table(
        "candidates",
        _id(),
        _company(),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(254)),
        sa.Column("phone", sa.String(40)),
        sa.Column("source", sa.String(40)),
        sa.Column("cv_file_id", sa.Uuid(), sa.ForeignKey("files.id", ondelete="RESTRICT")),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        *_record_columns(),
        sa.UniqueConstraint("company_id", "id", name="uq_candidates_company_id_id"),
        sa.CheckConstraint("length(trim(first_name)) > 0", name="first_name"),
        sa.CheckConstraint("length(trim(last_name)) > 0", name="last_name"),
    )
    op.create_table(
        "applications",
        _id(),
        _company(),
        sa.Column(
            "candidate_id",
            sa.Uuid(),
            sa.ForeignKey("candidates.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "posting_id",
            sa.Uuid(),
            sa.ForeignKey("postings.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("stage", sa.String(16), nullable=False, server_default="applied"),
        sa.Column("stage_history", JSONB(), nullable=False, server_default="[]"),
        sa.Column("cover_note", sa.Text()),
        sa.Column("applied_via", sa.String(14), nullable=False, server_default="admin"),
        *_record_columns(),
        sa.UniqueConstraint("company_id", "id", name="uq_applications_company_id_id"),
        sa.UniqueConstraint(
            "company_id", "candidate_id", "posting_id", name="uq_applications_candidate_posting"
        ),
        sa.CheckConstraint(
            "stage in ('applied','shortlisted','interview','offer_letter','offer_accepted',"
            "'hired','rejected','withdrawn')",
            name="stage",
        ),
        sa.CheckConstraint("applied_via in ('admin','careers_page')", name="applied_via"),
    )
    op.create_table(
        "interviews",
        _id(),
        _company(),
        sa.Column(
            "application_id",
            sa.Uuid(),
            sa.ForeignKey("applications.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("location_or_link", sa.String(300)),
        sa.Column(
            "interviewer_employee_ids", ARRAY(sa.Uuid()), nullable=False, server_default="{}"
        ),
        sa.Column("outcome", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("notes", sa.Text()),
        *_record_columns(),
        sa.CheckConstraint("duration_minutes between 5 and 480", name="duration"),
        sa.CheckConstraint("mode in ('in_person','video','phone')", name="mode"),
        sa.CheckConstraint("outcome in ('pending','passed','failed','no_show')", name="outcome"),
    )
    op.create_table(
        "offers",
        _id(),
        _company(),
        sa.Column(
            "application_id",
            sa.Uuid(),
            sa.ForeignKey("applications.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("role_title", sa.String(200), nullable=False),
        sa.Column("salary", sa.Numeric(12, 2), nullable=False),
        sa.Column("salary_per", sa.String(6), nullable=False),
        sa.Column("start_date", sa.Date()),
        sa.Column("status", sa.String(10), nullable=False, server_default="draft"),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        *_record_columns(),
        sa.CheckConstraint("length(trim(role_title)) > 0", name="role_title"),
        sa.CheckConstraint("salary_per in ('year','month','hour')", name="salary_per"),
        sa.CheckConstraint(
            "status in ('draft','sent','accepted','declined','withdrawn')", name="status"
        ),
    )
    for table in TABLES:
        enable_tenant_rls(table)
        add_updated_at_trigger(table)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
