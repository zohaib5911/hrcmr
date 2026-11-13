"""Versioned operator-loaded Companies House bulk files (C4.1.15)."""

from alembic import op
from app.modules.register.models import CompanyDataset, CompanyMatch

revision = "0063_register_companies"
down_revision = "0062_register_places"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Owner-only: the public API reads enriched sponsor fields, never bulk files/provenance.
    CompanyDataset.__table__.create(op.get_bind())
    CompanyMatch.__table__.create(op.get_bind())


def downgrade() -> None:
    CompanyMatch.__table__.drop(op.get_bind())
    CompanyDataset.__table__.drop(op.get_bind())
