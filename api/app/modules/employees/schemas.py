from __future__ import annotations

import uuid  # noqa: TC003  (Pydantic reads the annotations at run time)
from datetime import date  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, Field

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
