"""Data exports: a company's zip, built by the worker and linked for 7 days (T16.4).

Revision ID: 0046_data_exports
Revises: 0045_payment_grace
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision = "0046_data_exports"
down_revision = "0045_payment_grace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_exports",
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
        sa.Column("status", sa.String(10), nullable=False, server_default="queued"),
        sa.Column("file_id", sa.Uuid()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
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
            name="fk_data_exports_file",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("status in ('queued','ready','failed')", name="status"),
        sa.CheckConstraint("(status = 'ready') = (file_id is not null)", name="file_state"),
        sa.CheckConstraint("(status = 'ready') = (expires_at is not null)", name="expiry_state"),
        sa.CheckConstraint("(status = 'queued') = (finished_at is null)", name="finished_state"),
        sa.CheckConstraint("(status = 'failed') = (error_code is not null)", name="error_state"),
    )
    op.create_index("ix_data_exports_company_id", "data_exports", ["company_id"])
    op.create_index(
        "ix_data_exports_requester", "data_exports", ["company_id", "requested_by", "created_at"]
    )
    enable_tenant_rls("data_exports")
    add_updated_at_trigger("data_exports")


def downgrade() -> None:
    op.drop_table("data_exports")
