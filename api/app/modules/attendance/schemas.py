"""Attendance workspace and company-local manual entry inputs."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime, time  # noqa: TC003
from decimal import Decimal  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.schemas import RequestModel

AttendanceStatus = Literal["present", "absent", "late", "half_day", "on_leave", "sick"]


class AttendanceIn(RequestModel):
    employee_id: uuid.UUID
    date: date
    status: AttendanceStatus
    clock_in: time | None = None
    clock_out: time | None = None
    clock_in_fold: Literal[0, 1] | None = None
    clock_out_fold: Literal[0, 1] | None = None
    unpaid_break_minutes: int = Field(default=0, ge=0, le=1440)
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("clock_in", "clock_out")
    @classmethod
    def local_time(cls, value: time | None) -> time | None:
        if value is not None and (value.tzinfo is not None or value.second or value.microsecond):
            raise ValueError("Use company-local hours and minutes (HH:MM).")
        return value

    @field_validator("note")
    @classmethod
    def trim(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class AttendanceOut(BaseModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    date: date
    status: AttendanceStatus
    clock_in: datetime | None
    clock_out: datetime | None
    clock_in_local: str | None
    clock_out_local: str | None
    clock_in_fold: int | None
    clock_out_fold: int | None
    unpaid_break_minutes: int
    hours: Decimal | None
    note: str | None
    source: str
    leave_request_id: uuid.UUID | None


class AttendancePage(BaseModel):
    items: list[AttendanceOut]
    total: int
    next_offset: int | None
    timezone: str


class AttendanceSummary(BaseModel):
    on: date
    timezone: str
    employees: int
    counts: dict[str, int]
    not_recorded: int
