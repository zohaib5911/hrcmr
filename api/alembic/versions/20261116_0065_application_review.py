"""Flag public applications matched to existing candidates."""

import sqlalchemy as sa

from alembic import op

revision = "0065_application_review"
down_revision = "0064_list_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("applications", "needs_review")
