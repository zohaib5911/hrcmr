"""Complete rota setting forms; overnight breaks follow the shift's timeline."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import time  # noqa: TC003
from decimal import Decimal  # noqa: TC003
from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.core.schemas import RequestModel


def minutes(value: time) -> int:
    return value.hour * 60 + value.minute


class ShiftTypeIn(RequestModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    starts_at: time
    ends_at: time
    break_start: time | None = None
    break_end: time | None = None
    colour: str = Field(default="#007aff", pattern=r"^#[0-9a-fA-F]{6}$")

    @field_validator("name", "description", mode="before")
    @classmethod
    def trimmed(cls, value: object) -> object:
        return value.strip() or None if isinstance(value, str) else value

    @field_validator("starts_at", "ends_at", "break_start", "break_end")
    @classmethod
    def wall_time(cls, value: time | None) -> time | None:
        if value is not None and (value.tzinfo is not None or value.second or value.microsecond):
            raise ValueError("Use local hours and minutes (HH:MM).")
        return value

    @model_validator(mode="after")
    def valid_break(self) -> Self:
        duration = (minutes(self.ends_at) - minutes(self.starts_at)) % 1440
        if not duration:
            raise ValueError("Shift start and finish must differ.")
        if (self.break_start is None) != (self.break_end is None):
            raise ValueError("Enter both break times, or leave both empty.")
        if self.break_start is not None and self.break_end is not None:
            offset = (minutes(self.break_start) - minutes(self.starts_at)) % 1440
            length = (minutes(self.break_end) - minutes(self.break_start)) % 1440
            if not length or offset + length > duration:
                raise ValueError(
                    "The break must fall within the shift, including overnight shifts."
                )
        return self


class ShiftTypeOut(ShiftTypeIn):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: uuid.UUID


class SettingScope(RequestModel):
    department_id: uuid.UUID
    designation_id: uuid.UUID
    shift_type_id: uuid.UUID


class LatePolicyIn(SettingScope):
    grace_minutes: int = Field(ge=0, le=1440)
    allowed_late_days_per_month: int = Field(ge=0, le=31)
    deduction_type: Literal["none", "fixed", "percentage_of_day"]
    deduction_value: Decimal = Field(ge=0, max_digits=10, decimal_places=2)

    @model_validator(mode="after")
    def deduction(self) -> Self:
        if self.deduction_type == "none" and self.deduction_value != 0:
            raise ValueError("No deduction must have a value of zero.")
        if self.deduction_type == "percentage_of_day" and self.deduction_value > 100:
            raise ValueError("The percentage cannot exceed 100.")
        return self


class LatePolicyOut(LatePolicyIn):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: uuid.UUID


class DayOffPatternIn(SettingScope):
    weekdays_off: list[Annotated[int, Field(ge=1, le=7)]] = Field(max_length=7)
    works_public_holidays: bool = False

    @field_validator("weekdays_off")
    @classmethod
    def unique_days(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("Choose each weekday only once.")
        return sorted(value)


class DayOffPatternOut(DayOffPatternIn):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: uuid.UUID
