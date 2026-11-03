"""Leave configuration inputs: real recurring dates and bounded decimal day amounts."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from app.core.schemas import RequestModel
from app.modules.holidays.schemas import Colour  # noqa: TC001 (Pydantic resolves this alias)

Name = Annotated[str, Field(min_length=1, max_length=80)]
Days = Annotated[Decimal, Field(ge=0, max_digits=6, decimal_places=2)]
Accrual = Literal["front_loaded", "monthly"]


class LeaveTypeIn(RequestModel):
    name: Name
    is_paid: bool = True
    counts_toward_statutory: bool = False
    days_per_year: Days | None = None
    carry_over_limit_days: Days = Decimal("0")
    accrual_method: Accrual = "front_loaded"
    requires_approval: bool = True
    colour: Colour = "blue"
    rule_text: Annotated[str, Field(max_length=4000)] = ""

    @field_validator("name", "rule_text", mode="before")
    @classmethod
    def _trim(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class LeaveTypePatch(RequestModel):
    name: Name | None = None
    is_paid: bool | None = None
    counts_toward_statutory: bool | None = None
    days_per_year: Days | None = None
    carry_over_limit_days: Days | None = None
    accrual_method: Accrual | None = None
    requires_approval: bool | None = None
    colour: Colour | None = None
    rule_text: Annotated[str, Field(max_length=4000)] | None = None

    @field_validator("name", "rule_text", mode="before")
    @classmethod
    def _trim(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class LeaveTypeOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    seed_key: str | None
    name: str
    is_paid: bool
    counts_toward_statutory: bool
    days_per_year: Decimal | None
    carry_over_limit_days: Decimal
    accrual_method: Accrual
    requires_approval: bool
    colour: Colour
    rule_text: str
    source_url: str | None
    checked_on: date | None
    archived_at: datetime | None


class LeaveSettingsOut(BaseModel):
    model_config = {"from_attributes": True}
    leave_year_start_month_day: str
    allow_negative_leave_balance: bool


class LeaveSettingsPatch(RequestModel):
    leave_year_start_month_day: Annotated[str, Field(pattern=r"^\d{2}-\d{2}$")] | None = None
    allow_negative_leave_balance: bool | None = None

    @field_validator("leave_year_start_month_day")
    @classmethod
    def _recurring_date(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                date(2001, int(value[:2]), int(value[3:]))
            except ValueError as exc:
                raise ValueError(
                    "Use a date that occurs every year, such as 01-01 or 04-06."
                ) from exc
        return value
