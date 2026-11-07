"""Certificates for completed courses, with a public check by reference (plan 6.9, 8.14)."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision = "0036_certificates"
down_revision = "0035_learning"
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


def upgrade() -> None:
    op.create_table(
        "certificates",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("uuid_generate_v7()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "assignment_id",
            sa.Uuid(),
            sa.ForeignKey("course_assignments.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("reference", sa.String(20), nullable=False, unique=True),
        sa.Column("holder_name_snapshot", sa.String(200), nullable=False),
        sa.Column("course_title_snapshot", sa.String(160), nullable=False),
        sa.Column("completed_on", sa.Date(), nullable=False),
        sa.Column("issued_on", sa.Date(), nullable=False),
        *_record_columns(),
        sa.CheckConstraint("length(reference) >= 10", name="reference_length"),
    )
    enable_tenant_rls("certificates")
    add_updated_at_trigger("certificates")
    # The public check sets one reference for its own transaction. Only the certificate with that
    # reference becomes visible, so nothing else in the table is opened up.
    op.execute(
        "CREATE POLICY certificate_by_reference ON certificates FOR SELECT TO app_user "
        "USING (reference = current_setting('app.certificate_ref', true))"
    )


def downgrade() -> None:
    op.execute("DROP POLICY certificate_by_reference ON certificates")
    op.drop_table("certificates")
