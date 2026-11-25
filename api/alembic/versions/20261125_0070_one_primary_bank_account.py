"""At most one live main bank account per company (ISS-27).

Existing duplicates are reviewed here first: the most recently changed live main account stays
main and the others become ordinary accounts, so the index can be created without failing.
"""

from __future__ import annotations

from alembic import op

revision = "0070_one_primary_bank_account"
down_revision = "0069_one_queued_export"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE company_bank_accounts SET is_primary = false
        WHERE is_primary AND archived_at IS NULL AND id NOT IN (
            SELECT DISTINCT ON (company_id) id FROM company_bank_accounts
            WHERE is_primary AND archived_at IS NULL
            ORDER BY company_id, updated_at DESC, id DESC
        )
        """
    )
    op.create_index(
        "uq_company_bank_accounts_one_primary",
        "company_bank_accounts",
        ["company_id"],
        unique=True,
        postgresql_where="is_primary AND archived_at IS NULL",
    )


def downgrade() -> None:
    op.drop_index("uq_company_bank_accounts_one_primary", table_name="company_bank_accounts")
