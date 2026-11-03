"""Leave workspace projections and explicit, reasoned balance movements."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date  # noqa: TC003
from decimal import Decimal  # noqa: TC003

from pydantic import BaseModel, Field

from app.core.schemas import RequestModel


class BalanceOut(BaseModel):
    employee_id: uuid.UUID
    employee_name: str
    leave_type_id: uuid.UUID
    leave_type_name: str
    colour: str
    leave_year_start: date
    ledger_balance: Decimal
    available: Decimal | None
    entitlement: Decimal | None
    calendar_days: Decimal | None
    taken: Decimal
    pending: Decimal
    calculation_issue: str | None = None


class BalancePage(BaseModel):
    items: list[BalanceOut]
    next_offset: int | None


class BalanceMoveIn(RequestModel):
    leave_type_id: uuid.UUID
    on: date
    days: Decimal = Field(ge=-999999.99, le=999999.99, decimal_places=2, allow_inf_nan=False)
    reason: str = Field(min_length=1, max_length=1000)
    idempotency_key: uuid.UUID


class CalendarEntry(BaseModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    leave_type_name: str
    colour: str
    status: str
    working_dates: list[date]


class CalendarOut(BaseModel):
    month: str
    items: list[CalendarEntry]
