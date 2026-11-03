"""Reviewable 90/60/30-day reminders for versioned sponsor evidence and RTW follow-ups."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin

CONDITIONS = {
    "target": (
        "(sponsor_document_id is not null and rtw_check_id is null) or "
        "(sponsor_document_id is null and rtw_check_id is not null)"
    ),
    "threshold": "threshold_days in (90, 60, 30)",
    "due": "due_on = expires_on - threshold_days",
    "status": "status in ('scheduled', 'due', 'sent', 'snoozed', 'cancelled')",
    "draft": (
        "message_draft is null or (length(trim(message_draft)) > 0 and "
        "length(message_draft) <= 2000)"
    ),
    "sent": (
        "(status = 'sent' and sent_at is not null and sent_by_user_id is not null "
        "and email_outbox_id is not null and message_draft is not null) or "
        "(status <> 'sent' and sent_at is null and sent_by_user_id is null and "
        "email_outbox_id is null)"
    ),
    "snooze": (
        "(status = 'snoozed' and snoozed_until is not null) or (status <> "
        "'snoozed' and snoozed_until is null)"
    ),
    "cancelled": (
        "(status = 'cancelled' and cancel_reason is not null and "
        "length(trim(cancel_reason)) > 0) or (status <> 'cancelled' and "
        "cancel_reason is null)"
    ),
}


class Reminder(Base, RecordMixin, TenantMixin):
    __tablename__ = "reminders"
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False
    )
    sponsor_document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sponsor_documents.id", ondelete="RESTRICT")
    )
    rtw_check_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("rtw_checks.id", ondelete="RESTRICT")
    )
    threshold_days: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    expires_on: Mapped[date] = mapped_column(Date, nullable=False)
    due_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(9), nullable=False, server_default="scheduled")
    message_draft: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT")
    )
    email_outbox_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("email_outbox.id", ondelete="RESTRICT")
    )
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(80))
    admin_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "sponsor_document_id",
            "threshold_days",
            name="uq_reminders_sponsor_threshold",
        ),
        UniqueConstraint(
            "company_id", "rtw_check_id", "threshold_days", name="uq_reminders_rtw_threshold"
        ),
        Index("ix_reminders_employee", "company_id", "employee_id"),
        Index("ix_reminders_status_due", "company_id", "status", "due_on"),
        *(CheckConstraint(sql, name=name) for name, sql in CONDITIONS.items()),
    )
