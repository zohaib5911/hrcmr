"""RTW check inputs: every irrelevant field is refused instead of silently retained."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003
from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.schemas import RequestModel

CheckType = Literal["online_share_code", "idsp_digital", "manual_list_a", "manual_list_b"]
Outcome = Literal["pending", "verified", "failed"]
RTWStatus = Literal[
    "verified", "expiring", "expired", "failed", "pending", "evidence_missing", "not_recorded"
]


class CheckIn(RequestModel):
    check_type: CheckType
    share_code: str | None = Field(
        default=None, min_length=9, max_length=9, pattern=r"^[A-Z0-9]{9}$"
    )
    idsp_provider: str | None = Field(default=None, min_length=1, max_length=160)
    idsp_document: Literal["british_passport", "irish_passport", "irish_passport_card"] | None = (
        None
    )
    list_b_group: Literal["group1", "group2"] | None = None
    permission_expires: bool = False
    permission_expires_on: date | None = None
    check_date: date
    checked_by_user_id: uuid.UUID
    outcome: Outcome = "pending"
    evidence_file_id: uuid.UUID | None = None

    @field_validator("*", mode="before")
    @classmethod
    def trim(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("share_code", mode="before")
    @classmethod
    def code(cls, value: object) -> object:
        return "".join(value.split()).upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def conditions(self) -> Self:
        if self.check_type == "online_share_code":
            if not self.share_code:
                raise ValueError("Enter a 9-character share code.")
        elif self.share_code is not None:
            raise ValueError("Share codes are only used for online checks.")
        if self.check_type == "idsp_digital":
            if not self.idsp_provider or not self.idsp_document:
                raise ValueError(
                    "Choose the eligible passport document and name the certified provider."
                )
        elif self.idsp_provider is not None or self.idsp_document is not None:
            raise ValueError("Provider and passport type are only used for IDSP checks.")
        if self.check_type == "manual_list_b":
            if not self.list_b_group or not self.permission_expires:
                raise ValueError("Choose a List B group and enter the permission expiry date.")
        elif self.list_b_group is not None:
            raise ValueError("A List B group is only used for List B checks.")
        if self.check_type in {"idsp_digital", "manual_list_a"} and self.permission_expires:
            raise ValueError("This check type does not have a follow-up expiry date.")
        if self.permission_expires != (self.permission_expires_on is not None):
            raise ValueError("Enter the permission expiry date only when permission runs out.")
        return self


class CorrectionIn(CheckIn):
    reason: str = Field(min_length=1, max_length=1000)


class CheckOut(BaseModel):
    id: uuid.UUID
    check_type: CheckType
    share_code_masked: str | None
    idsp_provider: str | None
    idsp_document: str | None
    list_b_group: str | None
    permission_expires: bool
    permission_expires_on: date | None
    follow_up_due_on: date | None
    check_date: date | None
    checked_by_user_id: uuid.UUID | None
    checker_name: str | None
    outcome: Outcome
    evidence_file_id: uuid.UUID | None
    evidence_file_name: str | None
    status: RTWStatus
    superseded_at: datetime | None
    superseded_by: uuid.UUID | None
    corrected_from_id: uuid.UUID | None
    correction_reason: str | None
    created_at: datetime
    can_correct: bool


class RTWTab(BaseModel):
    status: RTWStatus
    follow_up_due_on: date | None
    current: CheckOut | None
    checks: list[CheckOut]


RTWFilter = Literal[
    "NeedsAttention", "Verified", "Expiring", "EvidenceMissing", "Expired", "Pending", "NotRecorded"
]

FILTER_STATUSES: dict[str, tuple[str, ...]] = {
    "NeedsAttention": (
        "expiring",
        "expired",
        "failed",
        "pending",
        "evidence_missing",
        "not_recorded",
    ),
    "Verified": ("verified",),
    "Expiring": ("expiring",),
    "EvidenceMissing": ("evidence_missing",),
    "Expired": ("expired", "failed"),
    "Pending": ("pending",),
    "NotRecorded": ("not_recorded",),
}
