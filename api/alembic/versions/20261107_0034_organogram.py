"""Org chart hierarchy levels (plan 6.2). Labels only; every company starts with "Director"."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls

revision = "0034_organogram"
down_revision = "0033_recruitment"
branch_labels = None
depends_on = None

FK_NAME = "fk_employee_assignments_organogram_level_id_organogram_levels"


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
        "organogram_levels",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("uuid_generate_v7()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        *_record_columns(),
        sa.CheckConstraint("length(trim(name)) > 0", name="name"),
        sa.CheckConstraint("rank >= 1", name="rank"),
    )
    op.create_index(
        "uq_organogram_levels_company_id_name",
        "organogram_levels",
        ["company_id", sa.text("lower(name)")],
        unique=True,
    )
    # The column has existed since the employment tables; it now points at a real table.
    op.create_foreign_key(
        FK_NAME,
        "employee_assignments",
        "organogram_levels",
        ["organogram_level_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        "insert into organogram_levels (company_id, name, rank) "
        "select id, 'Director', 1 from companies"
    )
    enable_tenant_rls("organogram_levels")
    add_updated_at_trigger("organogram_levels")


def downgrade() -> None:
    op.drop_constraint(FK_NAME, "employee_assignments", type_="foreignkey")
    op.drop_table("organogram_levels")
