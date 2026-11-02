"""invitations keep the invitee's name, so the list and the e-mail greeting can use it

Revision ID: 0012_invitation_names
Revises: 0011_pay_settings
Create Date: 2026-11-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012_invitation_names"
down_revision: str | None = "0011_pay_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("invitations", sa.Column("first_name", sa.String(100), nullable=True))
    op.add_column("invitations", sa.Column("last_name", sa.String(100), nullable=True))
    # Cancelling an invitation removes it (the audit trail keeps the record).
    op.execute("GRANT DELETE ON invitations TO app_user")


def downgrade() -> None:
    op.execute("REVOKE DELETE ON invitations FROM app_user")
    op.drop_column("invitations", "last_name")
    op.drop_column("invitations", "first_name")
