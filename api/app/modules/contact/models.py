"""Contact messages from the public contact form (plan 6.12, T17.4).

Global, like ``stripe_events``: a message has no company. The public form writes it (T18.1); only
platform admins read it and mark it handled. ``ip_hash`` is a hash, never the address itself.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003  (same)

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin

# The topics on the contact form (plan 8.20). The labels are the web's; these are the stored codes.
TOPICS = (
    "sponsor_compliance",
    "simple_hr",
    "pricing_billing",
    "setup_help",
    "partnership",
    "other",
    "data_protection",
)


class ContactMessage(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "contact_messages"
    __table_args__ = (
        CheckConstraint("topic in (" + ", ".join(f"'{t}'" for t in TOPICS) + ")", name="topic"),
        CheckConstraint("char_length(message) between 1 and 5000", name="message_length"),
        Index("ix_contact_messages_inbox", "handled_at", "created_at"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    company: Mapped[str | None] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    topic: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
