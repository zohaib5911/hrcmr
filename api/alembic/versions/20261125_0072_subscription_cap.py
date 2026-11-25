"""At most 2,000 subscriptions on the platform: a started checkout holds a place (FIX-subscription-cap).

``checkout_reserved_until`` is set when a company opens Stripe Checkout and cleared when that
checkout ends, so two companies paying at the same moment cannot both take the last place.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0072_subscription_cap"
down_revision = "0071_deletion_retry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("checkout_reserved_until", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("companies", "checkout_reserved_until")
