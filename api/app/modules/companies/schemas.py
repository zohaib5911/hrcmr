"""What ``/company`` accepts and returns (plan.md 8.15)."""

from __future__ import annotations

import re
import uuid  # noqa: TC003  (pydantic resolves the annotations at runtime)
from typing import Annotated, Literal
from zoneinfo import available_timezones

from pydantic import (
    AfterValidator,
    BaseModel,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.core.schemas import RequestModel
from app.modules.companies.reference import LEGAL_STRUCTURES, SECTORS, TRADING_PERIODS


def _one_of(values: dict[str, str], what: str) -> AfterValidator:
    def check(value: str | None) -> str | None:
        if value is not None and value not in values:
            raise ValueError(f"Choose one of the {what} in the list.")
        return value

    return AfterValidator(check)


# Each is one of the short values in ``reference.py``; ``GET /company/options`` has the labels.
LegalStructure = Annotated[str, _one_of(LEGAL_STRUCTURES, "legal structures")]
TradingPeriod = Annotated[str, _one_of(TRADING_PERIODS, "trading periods")]
Sector = Annotated[str, _one_of(SECTORS, "sectors")]
BankHolidayRegion = Literal["england-and-wales", "scotland", "northern-ireland"]
Plan = Literal["free", "annual", "ten_year"]

_PHONE = re.compile(r"[0-9 ()+\-]{6,25}")
_NUMBER = re.compile(r"[A-Z0-9]{8}")


class Features(BaseModel):
    """What this server can do, so the screen shows only what works."""

    companies_house_lookup: bool
    ai: bool


class CompanyDetails(BaseModel):
    id: uuid.UUID
    name: str
    trading_name: str | None
    registered_number: str | None
    type_of_organisation: LegalStructure | None
    trading_period: TradingPeriod | None
    sector: Sector | None
    contact_email: str | None
    contact_phone: str | None
    website: str | None
    has_logo: bool
    bank_holiday_region: BankHolidayRegion
    timezone: str
    changed_name_last_5_years: bool
    previous_company_name: str | None
    penalty_illegal_working_last_3_years: bool
    penalty_illegal_working_status: str | None
    ai_features_enabled: bool
    clock_geolocation_enabled: bool = False
    status: Literal["active", "suspended", "pending_deletion", "deleted"]
    plan: Plan


class CompanyOverview(BaseModel):
    company: CompanyDetails
    features: Features
    users: int = Field(description="People who can sign in to this company.")
    locations: int
    departments: int
    designations: int
    key_personnel_roles: int = Field(description="How many of the 4 key roles are filled.")
    compliance_documents: int = Field(description="How many of the 18 documents are held.")


class CompanyUpdate(RequestModel):
    """Only the fields that are sent change. ``null`` empties an optional field."""

    name: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    trading_name: Annotated[str, Field(max_length=200)] | None = None
    registered_number: str | None = None
    type_of_organisation: LegalStructure | None = None
    trading_period: TradingPeriod | None = None
    sector: Sector | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    website: Annotated[str, Field(max_length=300)] | None = None
    bank_holiday_region: BankHolidayRegion | None = None
    timezone: str | None = None
    changed_name_last_5_years: bool | None = None
    previous_company_name: Annotated[str, Field(max_length=200)] | None = None
    penalty_illegal_working_last_3_years: bool | None = None
    penalty_illegal_working_status: Annotated[str, Field(max_length=2000)] | None = None
    ai_features_enabled: bool | None = None
    clock_geolocation_enabled: bool | None = None

    @field_validator("clock_geolocation_enabled")
    @classmethod
    def _geo_switch(cls, value: bool | None) -> bool:
        if value is None:
            raise ValueError("Choose whether clock location is enabled.")
        return value

    @field_validator("name", "trading_name", "previous_company_name", mode="before")
    @classmethod
    def _trim(cls, value: object) -> object:
        return value.strip() or None if isinstance(value, str) else value

    @field_validator("registered_number")
    @classmethod
    def _number(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        number = value.strip().upper().replace(" ", "")
        if number.isdigit() and len(number) < 8:
            number = number.zfill(8)
        if not _NUMBER.fullmatch(number):
            raise ValueError("A Companies House number is 8 letters or digits, such as 01234567.")
        return number

    @field_validator("contact_phone")
    @classmethod
    def _phone(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        if not _PHONE.fullmatch(value.strip()):
            raise ValueError("Enter a phone number using digits, spaces, + ( ) and -.")
        return value.strip()

    @field_validator("website")
    @classmethod
    def _website(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        site = value.strip()
        if not re.fullmatch(r"https?://[^\s/$.?#][^\s]*\.[^\s]{2,}", site, re.IGNORECASE):
            raise ValueError("Enter a web address starting with https:// or http://")
        return site

    @field_validator("timezone")
    @classmethod
    def _timezone(cls, value: str | None) -> str | None:
        if value is not None and value not in available_timezones():
            raise ValueError("That is not a time zone we know. Pick one from the list.")
        return value

    @model_validator(mode="after")
    def _not_both_ways(self) -> CompanyUpdate:
        for flag, detail, message in (
            ("changed_name_last_5_years", "previous_company_name", "Enter the previous name."),
            (
                "penalty_illegal_working_last_3_years",
                "penalty_illegal_working_status",
                "Say what the penalty's status is.",
            ),
        ):
            sent = self.model_fields_set
            if getattr(self, flag) is True and detail in sent and not getattr(self, detail):
                raise ValueError(message)
        return self


class Option(BaseModel):
    value: str
    label: str


class CompanyOptions(BaseModel):
    legal_structures: list[Option]
    trading_periods: list[Option]
    sectors: list[Option]
    bank_holiday_regions: list[Option]
    timezones: list[str]


class AddressOut(BaseModel):
    line1: str | None
    line2: str | None
    city: str | None
    county: str | None
    postcode: str | None
    country: str | None


class CompaniesHouseRecord(BaseModel):
    number: str
    name: str
    status: str | None
    legal_structure: LegalStructure | None
    address: AddressOut
