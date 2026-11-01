"""first terms version, so sign-up always has something to accept

Revision ID: 0003_first_terms
Revises: 0002_identity_core
Create Date: 2026-11-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_first_terms"
down_revision: str | None = "0002_identity_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VERSION = "2026-11-draft"


def upgrade() -> None:
    # The wording is drafted in T18.2 and reviewed by a solicitor; publishing a newer version later
    # (Phase 17) makes everyone accept it again.
    op.execute(
        sa.text(
            "INSERT INTO terms_versions (version, published_at, url) "
            "VALUES (:version, now(), '/legal/terms')"
        ).bindparams(version=VERSION)
    )


def downgrade() -> None:
    delete = "DELETE FROM {} WHERE version = :version"
    op.execute(sa.text(delete.format("terms_acceptances")).bindparams(version=VERSION))
    op.execute(sa.text(delete.format("terms_versions")).bindparams(version=VERSION))
