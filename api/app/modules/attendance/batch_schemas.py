"""Reviewed import previews, bounded bulk entry and monthly absence summaries."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, Field

from app.core.schemas import RequestModel
from app.modules.attendance.schemas import AttendanceOut, AttendanceStatus  # noqa: TC001


class ImportRowOut(BaseModel):
    number: int
    values: dict[str, str]
    employee_name: str | None
    action: Literal["create", "update"] | None
    errors: list[str]


class AttendanceImportOut(BaseModel):
    id: uuid.UUID
    filename: str
    status: str
    from_date: date | None
    to_date: date | None
    rows_total: int
    rows_valid: int
    rows: list[ImportRowOut]
    committed_at: datetime | None


class GridRow(RequestModel):
    employee_id: uuid.UUID
    date: date
    status: AttendanceStatus


class GridIn(RequestModel):
    rows: list[GridRow] = Field(min_length=1, max_length=500)


class GridPerson(BaseModel):
    id: uuid.UUID
    name: str
    employee_number: str
    hire_date: date
    leave_date: date | None


class GridOut(BaseModel):
    start: date
    end: date
    timezone: str
    people: list[GridPerson]
    records: list[AttendanceOut]
    next_offset: int | None


class GridSaved(BaseModel):
    count: int


class AbsenceOut(BaseModel):
    month: str
    days: Decimal
    employees: int
    records: list[AttendanceOut]
    timezone: str
