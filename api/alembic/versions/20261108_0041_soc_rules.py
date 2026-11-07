"""Immigration rules data: versions, going rates, pay scales, Table 6, shortage lists, salary rules
(plan 6.10, T15.2)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.db.rls import add_updated_at_trigger

revision = "0041_soc_rules"
down_revision = "0040_soc_reference"
branch_labels = None
depends_on = None

CODE = "soc_code ~ '^[1-9][0-9]{3}$'"
TABLES = (
    "rules_versions",
    "going_rates",
    "pay_scale_rates",
    "ineligible_codes",
    "shortage_list_entries",
    "salary_rules",
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


def _id() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(
        "id", sa.Uuid(), primary_key=True, server_default=sa.text("uuid_generate_v7()")
    )


def _version() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(
        "rules_version_id",
        sa.Uuid(),
        sa.ForeignKey("rules_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


def _text_array(name: str) -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(name, postgresql.ARRAY(sa.Text()), nullable=False)


def upgrade() -> None:
    op.create_table(
        "rules_versions",
        _id(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="draft"),
        sa.Column("source_urls", postgresql.JSONB(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("published_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("diff_summary", postgresql.JSONB(), nullable=False),
        sa.Column("table_notes", postgresql.JSONB(), nullable=False),
        *_record_columns(),
        sa.CheckConstraint("status in ('draft', 'live', 'retired')", name="status"),
    )
    op.create_index(
        "uq_rules_versions_one_live",
        "rules_versions",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'live'"),
    )

    op.create_table(
        "going_rates",
        _id(),
        _version(),
        sa.Column("soc_code", sa.String(4), nullable=False, index=True),
        sa.Column("table", sa.String(3), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("administration", sa.Text(), nullable=False, server_default=""),
        _text_array("related_titles"),
        _text_array("soc2010_codes"),
        sa.Column("annual_rate", sa.Numeric(10, 2)),
        sa.Column("hourly_rate", sa.Numeric(8, 2)),
        sa.Column("rate_90", sa.Numeric(10, 2)),
        sa.Column("rate_80", sa.Numeric(10, 2)),
        sa.Column("rate_70", sa.Numeric(10, 2)),
        sa.Column("phd_points_eligible", sa.Boolean()),
        sa.Column("basis_hours", sa.Numeric(4, 1)),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        *_record_columns(),
        sa.UniqueConstraint(
            "rules_version_id", "table", "soc_code", "administration", name="uq_going_rates_one_row"
        ),
        sa.CheckConstraint(CODE, name="soc_code"),
        sa.CheckConstraint(
            "\"table\" in ('1', '1a', '2', '2a', '2aa', '2b', '3', '3a')", name="table"
        ),
    )

    op.create_table(
        "pay_scale_rates",
        _id(),
        _version(),
        sa.Column("source_table", sa.String(2), nullable=False),
        sa.Column("soc_code", sa.String(4), index=True),
        sa.Column("administration", sa.Text(), nullable=False),
        sa.Column("band_or_role", sa.Text(), nullable=False),
        sa.Column("annual_rate", sa.Numeric(10, 2), nullable=False),
        sa.Column("basis_hours", sa.Numeric(4, 1)),
        *_record_columns(),
        sa.CheckConstraint("source_table in ('3', '3a', '4', '5')", name="source_table"),
        sa.CheckConstraint(f"soc_code is null or {CODE}", name="soc_code"),
    )

    op.create_table(
        "ineligible_codes",
        _id(),
        _version(),
        sa.Column("soc_code", sa.String(4), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        _text_array("related_titles"),
        sa.Column("reason", sa.Text(), nullable=False),
        *_record_columns(),
        sa.UniqueConstraint("rules_version_id", "soc_code", name="uq_ineligible_codes_one_code"),
        sa.CheckConstraint(CODE, name="soc_code"),
    )

    op.create_table(
        "shortage_list_entries",
        _id(),
        _version(),
        sa.Column("list", sa.String(3), nullable=False),
        sa.Column("soc_code", sa.String(4), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("condition_text", sa.Text(), nullable=False, server_default=""),
        _text_array("job_types"),
        _text_array("nations"),
        sa.Column("removal_date", sa.Date(), nullable=False),
        sa.Column("dependants_allowed", sa.Boolean(), nullable=False),
        *_record_columns(),
        sa.UniqueConstraint(
            "rules_version_id", "list", "soc_code", name="uq_shortage_list_one_code"
        ),
        sa.CheckConstraint(CODE, name="soc_code"),
        sa.CheckConstraint("list in ('TSL', 'ISL')", name="list"),
    )

    op.create_table(
        "salary_rules",
        _id(),
        _version(),
        sa.Column("option", sa.String(1), nullable=False),
        sa.Column("general_threshold", sa.Numeric(10, 2), nullable=False),
        sa.Column("going_rate_pct", sa.SmallInteger(), nullable=False),
        sa.Column("criteria_key", sa.String(20), nullable=False),
        sa.Column("applies_to", sa.String(30), nullable=False),
        sa.Column("requirement_text", sa.Text(), nullable=False),
        sa.Column("further_rules", sa.Text(), nullable=False, server_default=""),
        *_record_columns(),
        sa.UniqueConstraint("rules_version_id", "option", name="uq_salary_rules_one_option"),
        sa.CheckConstraint(
            "option in ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K')", name="option"
        ),
        sa.CheckConstraint(
            "applies_to in ('new', 'transitional_pre_2024', 'transitional_pre_jul_2025', "
            "'health_care')",
            name="applies_to",
        ),
        sa.CheckConstraint("going_rate_pct between 1 and 100", name="going_rate_pct"),
    )

    # Global reference data, like soc_unit_groups: every company may read it, only the owner writes.
    for table in TABLES:
        add_updated_at_trigger(table)
        op.execute(f"GRANT SELECT ON {table} TO app_user")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {table}_read ON {table} FOR SELECT TO app_user USING (true)")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
