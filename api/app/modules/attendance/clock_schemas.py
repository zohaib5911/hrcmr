"""Server-timed self-service clocking and reviewed weekly timesheets."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003

from pydantic import BaseModel, Field

from app.core.schemas import RequestModel
from app.modules.attendance.schemas import AttendanceOut  # noqa: TC001


class ClockLocation(RequestModel):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    accuracy: float = Field(ge=0, le=100_000, allow_inf_nan=False)


class ClockIn(RequestModel):
    note: str | None = Field(default=None, max_length=2000)
    location: ClockLocation | None = None
    location_consent: bool = False


class ClockOut(ClockIn):
    record_id: uuid.UUID
    unpaid_break_minutes: int = Field(default=0, ge=0, le=1440)


class ClockState(BaseModel):
    employee_name: str | None
    timezone: str
    location_enabled: bool
    active: AttendanceOut | None


class TimesheetOut(BaseModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    period_start: date
    period_end: date
    hours: Decimal
    records: list[AttendanceOut]
    incomplete: bool
    fingerprint: str
    approved_at: datetime | None
    approved_by: uuid.UUID | None


class TimesheetPage(BaseModel):
    items: list[TimesheetOut]
    next_offset: int | None


class TimesheetApprove(RequestModel):
    employee_id: uuid.UUID
    period_start: date
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
