"""emergency contacts: the full relationship list from plan 8.3 (adds civil partner, guardian,
other relative)

Revision ID: 0014_emergency_relationships
Revises: 0013_employees
Create Date: 2026-11-02
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0014_emergency_relationships"
down_revision: str | None = "0013_employees"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = ("spouse", "partner", "parent", "child", "sibling", "relative", "friend", "other")
NEW = (
    "spouse",
    "civil_partner",
    "partner",
    "parent",
    "child",
    "sibling",
    "guardian",
    "other_relative",
    "friend",
    "other",
)
CONSTRAINT = "ck_emergency_contacts_relationship"


def _in(values: tuple[str, ...]) -> str:
    return f"relationship in ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.drop_constraint(op.f(CONSTRAINT), "emergency_contacts", type_="check")
    op.execute(
        "UPDATE emergency_contacts SET relationship = 'other_relative' WHERE relationship = 'relative'"
    )
    op.create_check_constraint(op.f(CONSTRAINT), "emergency_contacts", _in(NEW))


def downgrade() -> None:
    op.drop_constraint(op.f(CONSTRAINT), "emergency_contacts", type_="check")
    op.execute(
        "UPDATE emergency_contacts SET relationship = 'relative' "
        "WHERE relationship = 'other_relative'"
    )
    op.execute(
        "UPDATE emergency_contacts SET relationship = 'other' WHERE relationship in ('civil_partner', 'guardian')"
    )
    op.create_check_constraint(op.f(CONSTRAINT), "emergency_contacts", _in(OLD))
