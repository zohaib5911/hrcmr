"""Global sponsor register ingest tables (T20.1)."""

from alembic import op
from app.modules.register.models import Change, Entry, PossibleMatch, Publication, Sponsor

revision = "0058_register"
down_revision = "0057_company_comp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for model in (Publication, Sponsor, Entry, Change, PossibleMatch):
        model.__table__.create(op.get_bind())
    # Public read models, but only the owner job may mutate global register data.
    op.execute(
        "GRANT SELECT ON register_publications, register_sponsors, register_entries, "
        "register_changes, register_possible_matches TO app_user"
    )


def downgrade() -> None:
    for model in (PossibleMatch, Change, Entry, Sponsor, Publication):
        model.__table__.drop(op.get_bind())
