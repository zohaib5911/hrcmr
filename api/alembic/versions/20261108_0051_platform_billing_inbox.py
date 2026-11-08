"""Platform billing and the contact inbox (T17.4): refunds, the subscription list, the deletion and
export queues, and the contact messages.

Platform admins read ``subscriptions`` (0049 gave the read), and now update a refunded row too.
``deletion_requests`` and ``data_exports`` are tenant tables, so platform admins get a read policy
on each, as 0049 did for memberships. The two platform actions, a refund and a contact message
change, are written with no company through named policies, as 0048 to 0050 did.

``contact_messages`` is global, with no company, like ``stripe_events`` (0044): the public form
writes it (T18.1) and only platform code reads and marks it. Its personal data is therefore not
reachable from any tenant route.

Revision ID: 0051_platform_billing_inbox
Revises: 0050_support_mode
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0051_platform_billing_inbox"
down_revision = "0050_support_mode"
branch_labels = None
depends_on = None

PLATFORM_ADMIN = "EXISTS (SELECT 1 FROM platform_admins WHERE user_id = app_current_user_id())"
BILLING_ACTIONS = ("'platform.refund_issued'", "'platform.contact_updated'")
ACTIONS = f"({', '.join(BILLING_ACTIONS)})"
TOPICS = (
    "sponsor_compliance",
    "simple_hr",
    "pricing_billing",
    "setup_help",
    "partnership",
    "other",
    "data_protection",
)


def upgrade() -> None:
    op.create_table(
        "contact_messages",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuid_generate_v7()"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("company", sa.String(160)),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("topic", sa.String(40), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("ip_hash", sa.String(64)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("handled_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contact_messages")),
        sa.CheckConstraint(
            "topic in (" + ", ".join(f"'{topic}'" for topic in TOPICS) + ")",
            name="topic",
        ),
        sa.CheckConstraint("char_length(message) between 1 and 5000", name="message_length"),
    )
    op.create_index("ix_contact_messages_inbox", "contact_messages", ["handled_at", "created_at"])
    op.execute("GRANT SELECT, INSERT, UPDATE ON contact_messages TO app_user")

    op.execute(
        "CREATE POLICY platform_admin_subscriptions_update ON subscriptions AS PERMISSIVE "
        f"FOR UPDATE TO app_user USING ({PLATFORM_ADMIN}) WITH CHECK ({PLATFORM_ADMIN})"
    )
    op.execute(
        "CREATE POLICY platform_admin_deletion_requests_read ON deletion_requests "
        f"AS PERMISSIVE FOR SELECT TO app_user USING ({PLATFORM_ADMIN})"
    )
    op.execute(
        "CREATE POLICY platform_admin_data_exports_read ON data_exports "
        f"AS PERMISSIVE FOR SELECT TO app_user USING ({PLATFORM_ADMIN})"
    )
    op.execute(
        "CREATE POLICY platform_billing_audit ON audit_events FOR INSERT TO app_user "
        "WITH CHECK (company_id IS NULL AND actor_type = 'platform_admin' "
        "AND actor_user_id = app_current_user_id() "
        f"AND action IN {ACTIONS} AND {PLATFORM_ADMIN})"
    )
    op.execute(
        "CREATE POLICY platform_billing_audit_read ON audit_events FOR SELECT TO app_user "
        "USING (company_id IS NULL AND actor_type = 'platform_admin' "
        "AND actor_user_id = app_current_user_id() "
        f"AND action IN {ACTIONS} AND {PLATFORM_ADMIN})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY platform_billing_audit_read ON audit_events")
    op.execute("DROP POLICY platform_billing_audit ON audit_events")
    op.execute("DROP POLICY platform_admin_data_exports_read ON data_exports")
    op.execute("DROP POLICY platform_admin_deletion_requests_read ON deletion_requests")
    op.execute("DROP POLICY platform_admin_subscriptions_update ON subscriptions")
    op.drop_index("ix_contact_messages_inbox", table_name="contact_messages")
    op.drop_table("contact_messages")
