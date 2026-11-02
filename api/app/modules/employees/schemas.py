from __future__ import annotations

import uuid  # noqa: TC003  (Pydantic reads the annotations at run time)
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.schemas import RequestModel

Status = Literal["active", "on_leave", "leaver", "archived"]


class EmployeeRow(BaseModel):
    id: uuid.UUID
    employee_number: str
    first_name: str
    last_name: str
    email: str
    status: Status
    hire_date: date
    department_id: uuid.UUID | None
    department: str | None
    designation: str | None
    has_photo: bool


class EmployeeList(BaseModel):
    employees: list[EmployeeRow]
    total: int = Field(description="Matches before the 2000-row cap.")


class EmployeeSummary(BaseModel):
    total: int = Field(description="Everyone except archived records.")
    active: int
    on_leave: int
    leavers: int
    archived: int


def twelve_months_from(today: date) -> date:
    try:
        return today.replace(year=today.year + 1)
    except ValueError:  # 29 February
        return today.replace(year=today.year + 1, day=28)


class EmployeeIn(RequestModel):
    """The essentials for a new record; the rest is added on the profile."""

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    employee_number: str = Field(min_length=1, max_length=50)
    hire_date: date
    status: Literal["active", "on_leave"] = "active"

    @field_validator("first_name", "last_name", "employee_number", "phone")
    @classmethod
    def _trimmed(cls, value: str | None) -> str | None:
        value = value.strip() if value is not None else None
        return value or None

    @field_validator("first_name", "last_name", "employee_number")
    @classmethod
    def _not_blank(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("This is required.")
        return value

    @field_validator("hire_date")
    @classmethod
    def _not_too_far_ahead(cls, value: date) -> date:
        if value > twelve_months_from(datetime.now(UTC).date()):
            raise ValueError("The hire date can be at most 12 months from today.")
        return value


class EmployeeProfile(BaseModel):
    """The header and the Overview tab of an employee's record (plan 8.3)."""

    id: uuid.UUID
    employee_number: str
    first_name: str
    last_name: str
    email: str
    phone: str | None
    status: Status
    hire_date: date
    leave_date: date | None
    department: str | None
    designation: str | None
    has_photo: bool
    opted_out_48h_week: bool
    has_opt_out_agreement: bool
    documents: int = Field(description="Documents filed on the record.")
    can_delete: bool = Field(
        description="False when the record has history, so it can only be archived."
    )
    delete_blocker: str | None = Field(description="Why it cannot be deleted, in words.")


class StatusChange(RequestModel):
    status: Status
    leave_date: date | None = None


class OptOutChange(RequestModel):
    opted_out: bool


class PermanentDelete(RequestModel):
    confirm_name: str = Field(min_length=1, max_length=250, description="The full name, typed.")
