"""Problem reports sent from the public sponsor register pages (T20.4)."""

from alembic import op
from app.modules.register.models import ProblemReport

revision = "0059_register_reports"
down_revision = "0058_register"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ProblemReport.__table__.create(op.get_bind())
    op.execute("GRANT SELECT, INSERT ON register_problem_reports TO app_user")


def downgrade() -> None:
    ProblemReport.__table__.drop(op.get_bind())
