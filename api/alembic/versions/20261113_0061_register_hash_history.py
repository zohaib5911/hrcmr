"""Allow the same register bytes to recur in publication history (C4.1.2)."""

from alembic import op

revision = "0061_register_hash_history"
down_revision = "0060_register_rerun"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0058 creates tables from live model metadata, so fresh databases already have
    # the non-unique index. Existing databases still have the original constraint.
    op.drop_constraint(
        "uq_register_publications_sha256", "register_publications", type_="unique", if_exists=True
    )
    op.create_index(
        "ix_register_publications_sha256", "register_publications", ["sha256"], if_not_exists=True
    )


def downgrade() -> None:
    op.drop_index("ix_register_publications_sha256", table_name="register_publications")
    # Refuse downgrade if recurring hashes exist; never discard publication history.
    op.create_unique_constraint(
        "uq_register_publications_sha256", "register_publications", ["sha256"]
    )
