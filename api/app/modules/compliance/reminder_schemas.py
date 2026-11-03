"""Reminder review/register data; full references and codes never enter these responses."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.schemas import RequestModel

ReminderStatus = Literal["scheduled", "due", "sent", "snoozed", "cancelled"]
ReminderDocumentType = Literal["visa", "passport", "dbs", "euss", "national_id", "other", "rtw"]


class ReminderMessageIn(RequestModel):
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message", mode="before")
    @classmethod
    def trim(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ReminderOut(BaseModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    employee_number: str
    source_id: uuid.UUID
    kind: Literal["sponsor", "rtw"]
    doc_type: ReminderDocumentType
    document_label: str
    threshold_days: int
    expires_on: date
    due_on: date
    status: ReminderStatus
    message_draft: str
    sent_at: datetime | None
    sent_by_user_id: uuid.UUID | None
    sender_name: str | None
    snoozed_until: datetime | None
    cancel_reason: str | None
    recipient_available: bool
    can_send: bool
    email_status: Literal["pending", "sent", "failed"] | None


class ReminderSlot(BaseModel):
    employee_id: uuid.UUID
    employee_name: str
    employee_number: str
    source_id: uuid.UUID
    kind: Literal["sponsor", "rtw"]
    doc_type: ReminderDocumentType
    document_label: str
    expires_on: date | None
    reminders: list[ReminderOut]


class ReceivedReminder(BaseModel):
    id: uuid.UUID
    title: str
    message: str
    expires_on: date
    sent_at: datetime
    sender_name: str
