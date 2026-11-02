"""The Personal tab (plan 8.3): details, address, emergency contacts, identity and bank."""

from __future__ import annotations

import re
import uuid  # noqa: TC003  (Pydantic reads the annotations at run time)
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.schemas import RequestModel

Gender = Literal["not_specified", "male", "female", "non_binary", "prefer_not_to_say", "other"]
MaritalStatus = Literal[
    "not_specified",
    "single",
    "married",
    "civil_partnership",
    "separated",
    "divorced",
    "widowed",
    "prefer_not_to_say",
]
Relationship = Literal[
    "spouse",
    "civil_partner",
    "partner",
    "parent",
    "child",
    "sibling",
    "guardian",
    "other_relative",
    "friend",
    "other",
]

# Two letters, six digits, a letter A-D. The first letter is never D, F, I, Q, U or V; the second
# never D, F, I, O, Q, U or V; and the prefixes BG, GB, NK, KN, TN, NT and ZZ are not issued.
_NI = re.compile(r"^(?!BG|GB|NK|KN|TN|NT|ZZ)[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z][0-9]{6}[A-D]$")


def _tidy(value: str | None) -> str | None:
    value = value.strip() if value is not None else None
    return value or None


class PersonalDetailsIn(RequestModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    alt_phone: str | None = Field(default=None, max_length=40)
    date_of_birth: date | None = None
    gender: Gender = "not_specified"
    marital_status: MaritalStatus = "not_specified"
    nationality: str | None = Field(default=None, max_length=80)

    @field_validator("first_name", "last_name", "phone", "alt_phone", "nationality")
    @classmethod
    def _trimmed(cls, value: str | None) -> str | None:
        return _tidy(value)

    @field_validator("first_name", "last_name")
    @classmethod
    def _required(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("This is required.")
        return value

    @field_validator("date_of_birth")
    @classmethod
    def _plausible(cls, value: date | None) -> date | None:
        if value is not None and not date(1900, 1, 1) <= value < datetime.now(UTC).date():
            raise ValueError("Enter a date of birth in the past.")
        return value


class AddressIn(RequestModel):
    postcode: str | None = Field(default=None, max_length=12)
    line1: str = Field(min_length=1, max_length=120)
    line2: str | None = Field(default=None, max_length=120)
    line3: str | None = Field(default=None, max_length=120)
    city_county: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=80)

    @field_validator("postcode", "line1", "line2", "line3", "city_county", "country")
    @classmethod
    def _trimmed(cls, value: str | None) -> str | None:
        return _tidy(value)

    @field_validator("line1")
    @classmethod
    def _required(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("This is required.")
        return value


class ContactIn(RequestModel):
    name: str = Field(min_length=1, max_length=120)
    relationship: Relationship
    phone: str = Field(min_length=1, max_length=40)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=500)
    details: str | None = Field(default=None, max_length=1000)

    @field_validator("name", "phone", "address", "details")
    @classmethod
    def _trimmed(cls, value: str | None) -> str | None:
        return _tidy(value)

    @field_validator("name", "phone")
    @classmethod
    def _required(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("This is required.")
        return value


class IdentityIn(RequestModel):
    """Leave a field empty to clear it."""

    ni_number: str | None = Field(default=None, max_length=20)
    passport_number: str | None = Field(default=None, max_length=30)
    passport_country: str | None = Field(default=None, max_length=80)
    passport_expiry: date | None = None

    @field_validator("ni_number")
    @classmethod
    def _ni(cls, value: str | None) -> str | None:
        value = re.sub(r"[\s-]", "", value or "").upper()
        if value and not _NI.match(value):
            raise ValueError("Enter a National Insurance number such as AB 12 34 56 C.")
        return value or None

    @field_validator("passport_number")
    @classmethod
    def _passport(cls, value: str | None) -> str | None:
        value = re.sub(r"\s", "", value or "").upper()
        if value and not re.fullmatch(r"[A-Z0-9]{6,12}", value):
            raise ValueError("Enter the passport number as printed, 6 to 12 letters and digits.")
        return value or None

    @field_validator("passport_country")
    @classmethod
    def _country(cls, value: str | None) -> str | None:
        return _tidy(value)


class BankIn(RequestModel):
    account_holder: str = Field(min_length=1, max_length=120)
    bank_name: str = Field(min_length=1, max_length=120)
    sort_code: str = Field(max_length=10)
    account_number: str = Field(max_length=12)

    @field_validator("account_holder", "bank_name")
    @classmethod
    def _trimmed(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This is required.")
        return value

    @field_validator("sort_code")
    @classmethod
    def _sort_code(cls, value: str) -> str:
        digits = re.sub(r"[\s-]", "", value)
        if not re.fullmatch(r"[0-9]{6}", digits):
            raise ValueError("A sort code is 6 digits, such as 12-34-56.")
        return f"{digits[:2]}-{digits[2:4]}-{digits[4:]}"

    @field_validator("account_number")
    @classmethod
    def _account(cls, value: str) -> str:
        digits = re.sub(r"\s", "", value)
        if not re.fullmatch(r"[0-9]{8}", digits):
            raise ValueError("An account number is 8 digits.")
        return digits


class RevealIn(RequestModel):
    field: Literal["identity", "bank"]


# --- what comes back ------------------------------------------------------------------------------


class PersonalDetails(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str | None
    alt_phone: str | None
    date_of_birth: date | None
    gender: Gender
    marital_status: MaritalStatus
    nationality: str | None


class AddressOut(BaseModel):
    postcode: str | None
    line1: str
    line2: str | None
    line3: str | None
    city_county: str | None
    country: str | None


class ContactOut(BaseModel):
    id: uuid.UUID
    name: str
    relationship: Relationship
    phone: str
    email: str | None
    address: str | None
    details: str | None


class IdentityMasked(BaseModel):
    ni_number: str | None = Field(description="Masked, for example '•• •• •• 56 C'.")
    passport_number: str | None
    passport_country: str | None
    passport_expiry: date | None


class BankMasked(BaseModel):
    account_holder: str
    bank_name: str
    sort_code: str
    account_number: str


class PersonalTab(BaseModel):
    details: PersonalDetails
    address: AddressOut | None
    contacts: list[ContactOut]
    sensitive_visible: bool = Field(description="False when the caller may not see these at all.")
    identity: IdentityMasked | None
    bank: BankMasked | None


class IdentityRevealed(BaseModel):
    ni_number: str | None
    passport_number: str | None


class BankRevealed(BaseModel):
    sort_code: str
    account_number: str


class Revealed(BaseModel):
    identity: IdentityRevealed | None = None
    bank: BankRevealed | None = None
