"""Account deletion (T16.5): the request table, and a purge-only way past the history triggers.

Some tables keep their history by refusing UPDATE and DELETE in a trigger (the audit trail, right
to work checks, the leave ledger, sent policies...). Deleting a company must still remove them. Each
of those triggers is split in two: the UPDATE (and INSERT) part is unchanged, and the DELETE part
is skipped only while ``app_purge_allowed(company_id)`` is true. That needs BOTH the table owner
role (the API connects as ``app_user`` and never as the owner) AND the transaction-local setting
``app.purge_company_id`` naming that row's company, which only the deletion executor sets.

Revision ID: 0047_deletion_requests
Revises: 0046_data_exports
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from app.db.rls import add_updated_at_trigger, enable_tenant_rls
from app.db.roles import OWNER_ROLE

revision = "0047_deletion_requests"
down_revision = "0046_data_exports"
branch_labels = None
depends_on = None

PURGE_FUNCTION = f"""
CREATE FUNCTION app_purge_allowed(company uuid) RETURNS boolean
LANGUAGE sql STABLE
AS $$
    SELECT coalesce(
        current_user = '{OWNER_ROLE}'
        AND company IS NOT NULL
        AND current_setting('app.purge_company_id', true) = company::text,
        false
    )
$$
"""

# (trigger, table, function, the other events it keeps). Every one is BEFORE ... FOR EACH ROW.
GUARDED = (
    (
        "compliance_changes_immutable",
        "change_of_circumstances",
        "compliance_changes_immutable",
        "UPDATE",
    ),
    ("compliance_changes_immutable", "org_changes", "compliance_changes_immutable", "UPDATE"),
    ("reminders_immutable", "reminders", "reminders_immutable", "UPDATE"),
    ("rtw_checks_immutable", "rtw_checks", "rtw_checks_immutable", "UPDATE"),
    ("sponsor_documents_immutable", "sponsor_documents", "sponsor_documents_immutable", "UPDATE"),
    ("trg_audit_events_append_only", "audit_events", "audit_events_append_only", "UPDATE"),
    ("trg_leave_ledger_immutable", "leave_ledger", "leave_ledger_immutable", "UPDATE"),
    ("trg_leave_year_end_immutable", "leave_year_end_runs", "leave_year_end_immutable", "UPDATE"),
    (
        "trg_policy_acceptances_frozen",
        "policy_acceptances",
        "policy_acceptances_frozen",
        "INSERT OR UPDATE",
    ),
    ("trg_policy_documents_frozen", "policy_documents", "policy_documents_frozen", "UPDATE"),
)


def _split(trigger: str, table: str, function: str, events: str) -> list[str]:
    return [
        f"DROP TRIGGER {trigger} ON {table}",
        f"CREATE TRIGGER {trigger} BEFORE {events} ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {function}()",
        f"CREATE TRIGGER {trigger}_delete BEFORE DELETE ON {table} FOR EACH ROW "
        f"WHEN (NOT app_purge_allowed(OLD.company_id)) EXECUTE FUNCTION {function}()",
    ]


def upgrade() -> None:
    op.create_table(
        "deletion_requests",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("uuid_generate_v7()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # Kept after the purge (the company's deletion record); the person may be deleted.
        sa.Column("requested_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("code_hash", sa.String(64)),
        sa.Column("code_expires_at", sa.DateTime(timezone=True)),
        sa.Column("code_attempts", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("scheduled_for", sa.DateTime(timezone=True)),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True)),
        sa.Column("withdrawn_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("export_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("export_id", sa.Uuid()),  # the data export asked for with it (no key: purged)
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
        sa.CheckConstraint(
            "(confirmed_at is null) = (scheduled_for is null)", name="scheduled_state"
        ),
        sa.CheckConstraint(
            "completed_at is null or (confirmed_at is not null and withdrawn_at is null)",
            name="completed_state",
        ),
        sa.CheckConstraint("code_attempts between 0 and 10", name="code_attempts"),
    )
    op.create_index("ix_deletion_requests_company_id", "deletion_requests", ["company_id"])
    op.create_index(
        "uq_deletion_requests_open",
        "deletion_requests",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text("withdrawn_at is null and completed_at is null"),
    )
    op.create_index(
        "ix_deletion_requests_due",
        "deletion_requests",
        ["scheduled_for"],
        postgresql_where=sa.text(
            "confirmed_at is not null and withdrawn_at is null and completed_at is null"
        ),
    )
    enable_tenant_rls("deletion_requests", privileges=("SELECT", "INSERT", "UPDATE"))
    add_updated_at_trigger("deletion_requests")

    op.execute(PURGE_FUNCTION)
    for trigger, table, function, events in GUARDED:
        for statement in _split(trigger, table, function, events):
            op.execute(statement)


def downgrade() -> None:
    for trigger, table, function, events in GUARDED:
        op.execute(f"DROP TRIGGER {trigger}_delete ON {table}")
        op.execute(f"DROP TRIGGER {trigger} ON {table}")
        op.execute(
            f"CREATE TRIGGER {trigger} BEFORE {events} OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {function}()"
        )
    op.execute("DROP FUNCTION app_purge_allowed(uuid)")
    op.drop_table("deletion_requests")
