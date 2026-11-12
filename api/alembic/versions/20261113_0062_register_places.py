"""Operator-loaded ONS place-name datasets for register geocoding (C4.1.3)."""

from alembic import op
from app.modules.register.models import PlaceDataset

revision = "0062_register_places"
down_revision = "0061_register_hash_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Owner-only: the CLI and the register job read it; the public API never does.
    PlaceDataset.__table__.create(op.get_bind())


def downgrade() -> None:
    PlaceDataset.__table__.drop(op.get_bind())
