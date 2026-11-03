"""Explicit year-end review inputs and durable preview snapshots."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date  # noqa: TC003
from decimal import Decimal  # noqa: TC003

from pydantic import BaseModel, Field

from app.core.schemas import RequestModel


class CarryOverride(RequestModel):
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    days: Decimal = Field(ge=0, le=999999.99, decimal_places=2, allow_inf_nan=False)
    reason: str = Field(min_length=1, max_length=1000)


class YearEndIn(RequestModel):
    from_year: date
    overrides: list[CarryOverride] = Field(default_factory=list, max_length=2000)


class YearEndCommitIn(YearEndIn):
    preview_token: str = Field(pattern="^[a-f0-9]{64}$")


class CarryRow(BaseModel):
    employee_id: uuid.UUID
    employee_name: str
    leave_type_id: uuid.UUID
    leave_type_name: str
    remaining: Decimal | None
    limit: Decimal
    carry: Decimal
    expire: Decimal
    override_reason: str | None


class YearEndPreview(BaseModel):
    from_year: date
    to_year: date
    rows: list[CarryRow]
    blockers: list[str]
    preview_token: str
    committed_run_id: uuid.UUID | None = None
