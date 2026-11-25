"""At most one queued data export per company (ISS-25).

Any duplicates already queued are reviewed here, not left to fail the index: the newest stays
queued and the older ones are marked failed with ``duplicate``, so the worker builds one archive.
"""

from __future__ import annotations

from alembic import op

revision = "0069_one_queued_export"
down_revision = "0068_register_hold_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE data_exports SET status = 'failed', error_code = 'duplicate', finished_at = now()
        WHERE status = 'queued' AND id NOT IN (
            SELECT DISTINCT ON (company_id) id FROM data_exports WHERE status = 'queued'
            ORDER BY company_id, created_at DESC, id DESC
        )
        """
    )
    op.create_index(
        "uq_data_exports_one_queued",
        "data_exports",
        ["company_id"],
        unique=True,
        postgresql_where="status = 'queued'",
    )


def downgrade() -> None:
    op.drop_index("uq_data_exports_one_queued", table_name="data_exports")
