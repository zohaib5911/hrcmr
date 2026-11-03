"""Sponsor document inputs and masked outputs (T7.2)."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003
from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.schemas import RequestModel
from app.modules.rtw.schemas import RTWStatus  # noqa: TC001

DocumentType = Literal["visa", "passport", "dbs", "euss", "national_id", "other"]
VisaRoute = Literal[
    "skilled_worker",
    "health_care_worker",
    "global_business_mobility",
    "scale_up",
    "temporary_worker",
    "graduate",
    "student",
    "euss_settled",
    "euss_pre_settled",
    "family",
    "other",
]
DocumentStatus = Literal[
    "current", "expiring", "expired", "evidence_missing", "superseded", "withdrawn"
]


class SponsorDocumentIn(RequestModel):
    doc_type: DocumentType
    reference_number: str | None = Field(default=None, min_length=1, max_length=160)
    issuing_country: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    visa_route: VisaRoute | None = None
    cos_number: str | None = Field(default=None, min_length=1, max_length=160)
    soc_code: str | None = Field(default=None, pattern=r"^[0-9]{4}$")
    sponsored_salary: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    issue_date: date | None = None
    expiry_date: date | None = None
    review_date: date | None = None
    evidence_file_id: uuid.UUID | None = None
    remarks: str | None = Field(default=None, max_length=2000)

    @field_validator("*", mode="before")
    @classmethod
    def trim(cls, value: object) -> object:
        return value.strip() or None if isinstance(value, str) else value

    @field_validator("issuing_country", mode="before")
    @classmethod
    def country(cls, value: object) -> object:
        return value.strip().upper() or None if isinstance(value, str) else value

    @model_validator(mode="after")
    def conditions(self) -> Self:
        if self.doc_type == "visa":
            if self.visa_route is None:
                raise ValueError("Choose a visa route.")
        elif any(
            v is not None
            for v in (self.visa_route, self.cos_number, self.soc_code, self.sponsored_salary)
        ):
            raise ValueError("Route, CoS, SOC code and sponsored salary are only used for visas.")
        if self.issue_date and self.expiry_date and self.expiry_date < self.issue_date:
            raise ValueError("The expiry date cannot be before the issue date.")
        return self


class WithdrawalIn(RequestModel):
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def trim(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class RenewalIn(RequestModel):
    renewal_date: date
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("notes", mode="before")
    @classmethod
    def trim(cls, value: object) -> object:
        return value.strip() or None if isinstance(value, str) else value


class SponsorDocumentOut(BaseModel):
    id: uuid.UUID
    doc_type: DocumentType
    reference_number_masked: str | None
    issuing_country: str | None
    visa_route: VisaRoute | None
    cos_number_masked: str | None
    soc_code: str | None
    sponsored_salary: Decimal | None
    issue_date: date | None
    expiry_date: date | None
    review_date: date | None
    evidence_file_id: uuid.UUID | None
    evidence_file_name: str | None
    evidence_scan_status: str | None
    remarks: str | None
    version: int
    superseded_by: uuid.UUID | None
    withdrawn_at: datetime | None
    withdraw_reason: str | None
    renewal_date: date | None
    renewal_notes: str | None
    created_at: datetime
    status: DocumentStatus


class SponsoredEmployee(BaseModel):
    id: uuid.UUID
    employee_number: str
    first_name: str
    last_name: str
    visa_route: VisaRoute
    cos_number_masked: str | None
    soc_code: str | None
    expiry_date: date | None
    rtw_status: RTWStatus


class SponsoredEmployees(BaseModel):
    employees: list[SponsoredEmployee]
