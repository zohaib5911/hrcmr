"""Versioned operator-loaded Companies House bulk files (C4.1.15)."""

import sqlalchemy as sa

from alembic import op
from app.modules.register.models import CompanyDataset

revision = "0063_register_companies"
down_revision = "0062_register_places"
branch_labels = None
depends_on = None


def upgrade() -> None:
    CompanyDataset.__table__.create(op.get_bind())
    op.add_column("register_sponsors", sa.Column("companies_dataset_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_register_sponsors_companies_dataset",
        "register_sponsors",
        "register_company_datasets",
        ["companies_dataset_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_register_sponsors_companies_dataset", "register_sponsors", type_="foreignkey"
    )
    op.drop_column("register_sponsors", "companies_dataset_id")
    CompanyDataset.__table__.drop(op.get_bind())
