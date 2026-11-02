"""What the holiday endpoints accept and return (plan.md 8.6)."""

from __future__ import annotations

import uuid  # noqa: TC003  (pydantic resolves the annotations at runtime)
from datetime import date, datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Colour = Literal["blue", "green", "orange", "red", "gray"]
Region = Literal["england-and-wales", "scotland", "northern-ireland"]


def _clean(value: object) -> object:
    return value.strip() or None if isinstance(value, str) else value


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- working pattern ----------------------------------------------------------------------------


class PatternDay(_Strict):
    weekday: Annotated[int, Field(ge=1, le=7, description="1 is Monday, 7 is Sunday.")]
    is_working: bool
    hours: Annotated[Decimal, Field(ge=0, le=24, max_digits=4, decimal_places=2)]


class WorkingPattern(_Strict):
    days: Annotated[list[PatternDay], Field(min_length=7, max_length=7)]
    bank_holidays_non_working: bool

    @model_validator(mode="after")
    def _one_per_day(self) -> WorkingPattern:
        if sorted(day.weekday for day in self.days) != [1, 2, 3, 4, 5, 6, 7]:
            raise ValueError("Give each day of the week once.")
        for day in self.days:
            if day.is_working and day.hours == 0:
                raise ValueError("A working day needs some hours.")
        return self


# --- holidays ------------------------------------------------------------------------------------


class BankHolidayOut(BaseModel):
    on_date: date
    title: str


class HolidayTypeOut(BaseModel):
    id: uuid.UUID
    name: str
    colour: Colour


class HolidayTypeIn(_Strict):
    name: Annotated[str, Field(min_length=1, max_length=80)]
    colour: Colour = "blue"

    _trim = field_validator("name", mode="before")(_clean)


class CompanyHolidayOut(BaseModel):
    id: uuid.UUID
    name: str
    start_date: date
    end_date: date
    holiday_type_id: uuid.UUID | None
    description: str | None
    deduct_from_annual_leave: bool


class CompanyHolidayIn(_Strict):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    start_date: date
    end_date: date
    holiday_type_id: uuid.UUID | None = None
    description: Annotated[str, Field(max_length=1000)] | None = None
    deduct_from_annual_leave: bool = False

    _trim = field_validator("name", "description", mode="before")(_clean)

    @model_validator(mode="after")
    def _ordered(self) -> CompanyHolidayIn:
        if self.end_date < self.start_date:
            raise ValueError("The last day cannot be before the first day.")
        return self


class CompanyHolidayPatch(_Strict):
    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    start_date: date | None = None
    end_date: date | None = None
    holiday_type_id: uuid.UUID | None = None
    description: Annotated[str, Field(max_length=1000)] | None = None
    deduct_from_annual_leave: bool | None = None

    _trim = field_validator("name", "description", mode="before")(_clean)


class HolidayManagement(BaseModel):
    year: int
    region: Region
    bank_holidays: list[BankHolidayOut]
    bank_holidays_updated_at: datetime | None = Field(
        description="When the list was last fetched from GOV.UK (empty before the first fetch)."
    )
    company_holidays: list[CompanyHolidayOut]
    types: list[HolidayTypeOut]
