"""Policy draft, audience, recipient and immutable receipt contracts."""

from __future__ import annotations

# ruff: noqa: TC001 -- Pydantic resolves these aliases at runtime.
import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003
from typing import Annotated, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.core.schemas import RequestModel
from app.modules.policies.reference import (
    AcceptanceStatus,
    AudienceType,
    ConfirmationMode,
    PolicyCategory,
    PolicyStatus,
)

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class PolicyDraft(RequestModel):
    title: Title
    category: PolicyCategory
    confirmation_mode: ConfirmationMode = "accept"
    audience_type: AudienceType = "everyone"
    audience_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    accept_within_days: int = Field(default=14, ge=1, le=365)
    auto_send_new_starters: bool = False

    @model_validator(mode="after")
    def audience(self) -> Self:
        if len(set(self.audience_ids)) != len(self.audience_ids):
            raise ValueError("Choose each recipient or audience only once.")
        selected = self.audience_type in {"departments", "locations", "named"}
        if selected != bool(self.audience_ids):
            raise ValueError(
                "Choose at least one audience item, or use Everyone or Employees with a visa."
            )
        return self


class PolicyAccept(RequestModel):
    confirmed: bool
    typed_signature: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
        | None
    ) = None


class PolicyOut(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    previous_version_id: uuid.UUID | None
    version: int
    title: str
    category: PolicyCategory
    confirmation_mode: ConfirmationMode
    audience_type: AudienceType
    audience_ids: list[uuid.UUID]
    accept_within_days: int
    auto_send_new_starters: bool
    status: PolicyStatus
    sent_at: datetime | None
    archived_at: datetime | None
    file_id: uuid.UUID | None
    file_name: str | None
    file_mime: str | None
    scan_status: str | None
    recipients: int
    completed: int
    overdue: int


class PolicyRecipient(BaseModel):
    id: uuid.UUID | None
    employee_id: uuid.UUID
    employee_name: str
    employee_number: str
    due_on: date | None
    status: AcceptanceStatus
    accepted_at: datetime | None


class PolicyReceipt(BaseModel):
    id: uuid.UUID
    policy_document_id: uuid.UUID
    title: str
    version: int
    employee_id: uuid.UUID
    employee_name: str
    confirmation_mode: ConfirmationMode
    accepted_at: datetime
    typed_signature: str | None
    ip: str | None
    user_agent: str | None


class OwnPolicy(BaseModel):
    id: uuid.UUID
    title: str
    version: int
    confirmation_mode: ConfirmationMode
    due_on: date
    status: AcceptanceStatus
    accepted_at: datetime | None
    file_mime: str
    archived: bool


class OwnPolicySummary(BaseModel):
    pending: int
    overdue: int
    completed: int
