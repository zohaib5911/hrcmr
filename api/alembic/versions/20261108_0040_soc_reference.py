"""SOC 2020 reference data: unit groups and the coding index, with local embeddings (plan 6.10, T15.1)."""

from __future__ import annotations

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op
from app.db.rls import add_updated_at_trigger

revision = "0040_soc_reference"
down_revision = "0039_ai_interactions"
branch_labels = None
depends_on = None

EMBEDDING_DIMENSIONS = 384


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
        "soc_unit_groups",
        _id(),
        sa.Column("code", sa.String(4), nullable=False, unique=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("tasks", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("entry_requirements", sa.Text(), nullable=False),
        sa.Column("typical_titles", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("rqf_level", sa.String(10)),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=False),
        *_record_columns(),
        sa.CheckConstraint("code ~ '^[1-9][0-9]{3}$'", name="code"),
        sa.CheckConstraint("rqf_level in ('6', '3-5', 'below')", name="rqf_level"),
    )
    add_updated_at_trigger("soc_unit_groups")

    op.create_table(
        "soc_index_entries",
        _id(),
        sa.Column("index_title", sa.Text(), nullable=False),
        sa.Column("qualifier_add", sa.Text(), nullable=False, server_default=""),
        sa.Column("qualifier_ind", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "soc_code",
            sa.String(4),
            sa.ForeignKey("soc_unit_groups.code", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=False),
        *_record_columns(),
        sa.UniqueConstraint(
            "index_title",
            "qualifier_add",
            "qualifier_ind",
            "soc_code",
            name="uq_soc_index_entries_one_entry",
        ),
    )
    op.create_index(
        "ix_soc_index_entries_index_title_trgm",
        "soc_index_entries",
        ["index_title"],
        postgresql_using="gin",
        postgresql_ops={"index_title": "gin_trgm_ops"},
    )
    add_updated_at_trigger("soc_index_entries")

    # Global reference data, like courses: every company may read it, nobody but the owner writes it.
    # The grant is SELECT only; the policy and the grant together keep app_user read-only.
    for table in ("soc_unit_groups", "soc_index_entries"):
        op.execute(f"GRANT SELECT ON {table} TO app_user")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {table}_read ON {table} FOR SELECT TO app_user USING (true)")


def downgrade() -> None:
    op.drop_table("soc_index_entries")
    op.drop_table("soc_unit_groups")
