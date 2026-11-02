"""Request and response shapes for the pay settings."""

from __future__ import annotations

import re
import uuid  # noqa: TC003  (Pydantic reads the annotations at run time)
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.schemas import RequestModel

Frequency = Literal["weekly", "fortnightly", "four_weekly", "monthly"]
PayDayKind = Literal["weekday", "day_of_month", "last_day", "last_working_day"]


def _clean(value: object) -> object:
    return value.strip() or None if isinstance(value, str) else value


def _trimmed(*names: str):  # type: ignore[no-untyped-def]
    return field_validator(*names, mode="before")(_clean)


Name = Annotated[str, Field(min_length=1, max_length=80)]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]

# --- bank accounts -------------------------------------------------------------------------------


class BankAccountOut(BaseModel):
    id: uuid.UUID
    label: str
    bank_name: str
    account_holder: str
    sort_code_masked: str = Field(description="Only the last two digits, such as ••-••-56.")
    account_number_masked: str = Field(description="Only the last four digits, such as ••••5678.")
    is_primary: bool


def digits(value: object, length: int, what: str) -> object:
    if not isinstance(value, str):
        return value
    only = re.sub(r"[\s-]", "", value)
    if not re.fullmatch(rf"[0-9]{{{length}}}", only):
        raise ValueError(f"A {what} is {length} digits.")
    return only


class BankAccountIn(RequestModel):
    label: Name
    bank_name: Annotated[str, Field(min_length=1, max_length=120)]
    account_holder: Annotated[str, Field(min_length=1, max_length=120)]
    sort_code: str = Field(description="Six digits; spaces and dashes are ignored.")
    account_number: str = Field(description="Eight digits.")
    is_primary: bool = False

    _trim = _trimmed("label", "bank_name", "account_holder")

    @field_validator("sort_code", mode="before")
    @classmethod
    def _sort(cls, value: object) -> object:
        return digits(value, 6, "sort code")

    @field_validator("account_number", mode="before")
    @classmethod
    def _account(cls, value: object) -> object:
        return digits(value, 8, "UK account number")


class BankAccountPatch(RequestModel):
    """Only what is sent changes. Numbers are never sent back, so leaving them out keeps them."""

    label: Name | None = None
    bank_name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    account_holder: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    sort_code: str | None = None
    account_number: str | None = None
    is_primary: bool | None = None

    _trim = _trimmed("label", "bank_name", "account_holder")

    @field_validator("sort_code", mode="before")
    @classmethod
    def _sort(cls, value: object) -> object:
        return None if value is None else digits(value, 6, "sort code")

    @field_validator("account_number", mode="before")
    @classmethod
    def _account(cls, value: object) -> object:
        return None if value is None else digits(value, 8, "UK account number")


# --- tax codes -----------------------------------------------------------------------------------


class TaxCodeOut(BaseModel):
    id: uuid.UUID
    code: str
    reference: str | None
    deduction_percentage: Decimal


class TaxCodeIn(RequestModel):
    code: Annotated[str, Field(min_length=1, max_length=12, pattern=r"^[A-Za-z0-9 ]+$")]
    reference: Annotated[str, Field(max_length=80)] | None = None
    deduction_percentage: Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]

    _trim = _trimmed("code", "reference")

    @field_validator("code")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()


# --- payment types -------------------------------------------------------------------------------


class PaymentTypeOut(BaseModel):
    id: uuid.UUID
    name: str
    min_hourly_rate: Decimal


class PaymentTypeIn(RequestModel):
    name: Name
    min_hourly_rate: Annotated[Decimal, Field(ge=0, max_digits=8, decimal_places=2)]

    _trim = _trimmed("name")


# --- pay bands -----------------------------------------------------------------------------------


class PayBandOut(BaseModel):
    id: uuid.UUID
    name: str
    min_annual: Decimal
    max_annual: Decimal
    currency: str


class PayBandIn(RequestModel):
    name: Name
    min_annual: Money
    max_annual: Money
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] = "GBP"

    _trim = _trimmed("name")

    @model_validator(mode="after")
    def _range(self) -> PayBandIn:
        if self.max_annual < self.min_annual:
            raise ValueError("The most cannot be less than the least.")
        return self


# --- pay schedules -------------------------------------------------------------------------------


class PayScheduleOut(BaseModel):
    id: uuid.UUID
    name: str
    frequency: Frequency
    pay_day_kind: PayDayKind
    pay_day_value: int | None


class PayScheduleIn(RequestModel):
    name: Name
    frequency: Frequency
    pay_day_kind: PayDayKind
    pay_day_value: Annotated[int, Field(ge=1, le=28)] | None = Field(
        default=None,
        description="The weekday (1 Monday to 7 Sunday) or the day of the month (1 to 28).",
    )

    _trim = _trimmed("name")

    @model_validator(mode="after")
    def _day(self) -> PayScheduleIn:
        by_week = self.frequency != "monthly"
        if by_week and self.pay_day_kind != "weekday":
            raise ValueError("A weekly, fortnightly or four-weekly schedule pays on a weekday.")
        if not by_week and self.pay_day_kind == "weekday":
            raise ValueError("A monthly schedule pays on a day of the month, or the last day.")
        if self.pay_day_kind == "weekday" and (
            self.pay_day_value is None or not 1 <= self.pay_day_value <= 7
        ):
            raise ValueError("Choose a weekday.")
        if self.pay_day_kind == "day_of_month" and self.pay_day_value is None:
            raise ValueError("Choose a day of the month, 1 to 28.")
        if self.pay_day_kind in ("last_day", "last_working_day"):
            self.pay_day_value = None
        return self
