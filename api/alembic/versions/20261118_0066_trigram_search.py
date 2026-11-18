"""Trigram indexes for search anywhere in a name (O6.1.3): the public sponsor explorer (organisation
name and town) and the in-app search (employee and candidate full names). pg_trgm serves
`lower(x) LIKE '%text%'`, which a b-tree cannot. EXPLAIN checks in tests/db/test_performance.py."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0066_trigram_search"
down_revision = "0065_application_review"
branch_labels = None
depends_on = None

FULL_NAME = sa.func.lower(
    sa.column("first_name").op("||")(sa.literal_column("' '")).op("||")(sa.column("last_name"))
)


def upgrade() -> None:
    # 0058 builds the register tables from the models, so a new database already has these two;
    # a database migrated before this revision gets them here.
    op.create_index(
        "ix_register_sponsors_name_trgm",
        "register_sponsors",
        [sa.func.lower(sa.column("organisation_name")).label("name")],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
        if_not_exists=True,
    )
    op.create_index(
        "ix_register_sponsors_town_trgm",
        "register_sponsors",
        [sa.func.lower(sa.column("town")).label("town")],
        postgresql_using="gin",
        postgresql_ops={"town": "gin_trgm_ops"},
        if_not_exists=True,
    )
    for table in ("employees", "candidates"):
        op.create_index(
            f"ix_{table}_full_name_trgm",
            table,
            [FULL_NAME.label("full_name")],
            postgresql_using="gin",
            postgresql_ops={"full_name": "gin_trgm_ops"},
        )


def downgrade() -> None:
    for table in ("candidates", "employees"):
        op.drop_index(f"ix_{table}_full_name_trgm", table)
    op.drop_index("ix_register_sponsors_town_trgm", "register_sponsors", if_exists=True)
    op.drop_index("ix_register_sponsors_name_trgm", "register_sponsors", if_exists=True)
