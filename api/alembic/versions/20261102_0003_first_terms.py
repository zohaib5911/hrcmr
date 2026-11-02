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


def _terms(name: str) -> sa.TableClause:
    return sa.table(name, sa.column("version"), sa.column("published_at"), sa.column("url"))


def upgrade() -> None:
    # The wording is drafted in T18.2 and reviewed by a solicitor; publishing a newer version later
    # (Phase 17) makes everyone accept it again.
    op.execute(
        sa.insert(_terms("terms_versions")).values(
            version=VERSION, published_at=sa.func.now(), url="/legal/terms"
        )
    )


def downgrade() -> None:
    for name in ("terms_acceptances", "terms_versions"):
        table = _terms(name)
        op.execute(sa.delete(table).where(table.c.version == VERSION))
