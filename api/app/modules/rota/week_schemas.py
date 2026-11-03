"""Rota week projections and optimistic, company-local shift edits."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime, time  # noqa: TC003
from decimal import Decimal  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.schemas import RequestModel


class WeekVersion(RequestModel):
    version: int = Field(ge=0)


class ShiftIn(WeekVersion):
    employee_id: uuid.UUID
    date: date
    starts_at: time
    ends_at: time
    starts_fold: Literal[0, 1] | None = None
    ends_fold: Literal[0, 1] | None = None
    unpaid_break_minutes: int = Field(default=0, ge=0, le=1440)
    shift_type_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def wall(cls, value: time) -> time:
        if value.tzinfo is not None or value.second or value.microsecond:
            raise ValueError("Use local hours and minutes (HH:MM).")
        return value


class ShiftOut(BaseModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    date: date
    starts_at: datetime
    ends_at: datetime
    starts_local: str
    ends_local: str
    starts_fold: int
    ends_fold: int
    unpaid_break_minutes: int
    hours: Decimal
    shift_type_id: uuid.UUID | None
    shift_name: str | None
    note: str | None


class RotaPerson(BaseModel):
    id: uuid.UUID
    name: str
    employee_number: str
    opted_out_48h_week: bool


class RotaWarning(BaseModel):
    employee_id: uuid.UUID
    shift_id: uuid.UUID | None
    code: str
    message: str


class WeekOut(BaseModel):
    week_start: date
    status: str
    version: int
    published_at: datetime | None
    timezone: str
    people: list[RotaPerson]
    shifts: list[ShiftOut]
    warnings: list[RotaWarning]
    totals: dict[str, Decimal]
    not_scheduled: list[uuid.UUID]
    next_offset: int | None


class ShiftSaved(BaseModel):
    shift: ShiftOut
    version: int


class ActionOut(BaseModel):
    count: int
    version: int


class EmployeeWeekAction(WeekVersion):
    employee_id: uuid.UUID


class CopyDay(WeekVersion):
    source: date
    targets: list[date] = Field(min_length=1, max_length=6)


class ClearWeek(WeekVersion):
    date: date | None = None


class OwnShifts(BaseModel):
    timezone: str
    shifts: list[ShiftOut]
