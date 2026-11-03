"""Durable worker report jobs (T10.2).

Revision ID: 0031_report_jobs
Revises: 0030_company_documents
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision = "0031_report_jobs"
down_revision = "0030_company_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("uuid_generate_v7()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "requested_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("report_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="queued"),
        sa.Column("file_id", sa.Uuid()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(40)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
        sa.ForeignKeyConstraint(
            ["company_id", "file_id"],
            ["files.company_id", "files.id"],
            name="fk_report_jobs_file",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "report_type in ('employee_directory', 'employee_detail', 'archived_employees', 'company', 'sponsor_workers', 'leave_taken', 'training_completion')",
            name="report_type",
        ),
        sa.CheckConstraint("status in ('queued','ready','failed')", name="status"),
        sa.CheckConstraint("(status = 'ready') = (file_id is not null)", name="file_state"),
        sa.CheckConstraint("(status = 'queued') = (finished_at is null)", name="finished_state"),
        sa.CheckConstraint("(status = 'failed') = (error_code is not null)", name="error_state"),
    )
    op.create_index("ix_report_jobs_company_id", "report_jobs", ["company_id"])
    op.create_index(
        "ix_report_jobs_requester", "report_jobs", ["company_id", "requested_by", "created_at"]
    )
    enable_tenant_rls("report_jobs")
    add_updated_at_trigger("report_jobs")


def downgrade() -> None:
    op.drop_table("report_jobs")
