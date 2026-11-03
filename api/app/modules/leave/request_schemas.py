"""Leave request and preview inputs; response quantities use company-day units."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.schemas import RequestModel


class LeaveDatesIn(RequestModel):
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date
    half_day_start: bool = False
    half_day_end: bool = False
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("note")
    @classmethod
    def trim(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def valid_dates(self) -> Self:
        if self.end_date < self.start_date or (self.end_date - self.start_date).days > 366:
            raise ValueError("Choose an end date after the start, within one year.")
        if self.start_date == self.end_date and self.half_day_start and self.half_day_end:
            raise ValueError("For a single half day, select only one half-day option.")
        return self


class LeaveRequestIn(LeaveDatesIn):
    employee_id: uuid.UUID


class LeaveDecisionIn(RequestModel):
    note: str | None = Field(default=None, max_length=2000)


class LeaveConflict(BaseModel):
    code: str
    message: str
    blocking: bool


class LeavePreview(BaseModel):
    working_days: Decimal
    working_dates: list[date]
    conflicts: list[LeaveConflict]


class LeaveRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date
    half_day_start: bool
    half_day_end: bool
    working_days: Decimal
    note: str | None
    status: Literal["pending", "approved", "rejected", "cancelled"]
    decided_by: uuid.UUID | None
    decided_at: datetime | None
    decision_note: str | None
    created_at: datetime
