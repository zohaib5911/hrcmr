"""The outbox: every e-mail we mean to send is saved here first (plan.md T2.8).

Saving it first means a mail service that is down, or a restart in the middle, loses nothing: the
background job picks it up again. The values that fill the template (they can hold a one-time
link) are encrypted, and erased as soon as the message is sent or given up on.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003  (SQLAlchemy resolves the Mapped[...] annotations)

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin

OUTBOX_STATUSES = ("pending", "sent", "failed")


class EmailOutbox(Base, RecordMixin):
    __tablename__ = "email_outbox"
    __table_args__ = (
        CheckConstraint("status in ('pending', 'sent', 'failed')", name="status"),
        CheckConstraint("attempts >= 0", name="attempts"),
        Index("ix_email_outbox_status_next_attempt_at", "status", "next_attempt_at"),
    )

    to_address: Mapped[str] = mapped_column(String(320), nullable=False)
    template: Mapped[str] = mapped_column(String(40), nullable=False)
    # Encrypted JSON of the template values; NULL once the message is sent or has failed for good.
    payload: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # A short reason, never the address or the message.
    last_error: Mapped[str | None] = mapped_column(String(200))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_id: Mapped[str | None] = mapped_column(String(100))
