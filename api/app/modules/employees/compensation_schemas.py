"""Salary records and the indicative age-band minimum-wage check (T6.6)."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date  # noqa: TC003
from decimal import Decimal  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.schemas import RequestModel


class CompensationIn(RequestModel):
    amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    frequency: Literal["annual", "monthly", "hourly"]
    contracted_hours_per_week: Decimal | None = Field(default=None, gt=0, le=168, decimal_places=2)
    tax_code_id: uuid.UUID | None = None
    payment_type_id: uuid.UUID | None = None
    pay_band_id: uuid.UUID | None = None
    pay_schedule_id: uuid.UUID | None = None
    effective_from: date


class CompensationOut(CompensationIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tax_code: str | None = None
    payment_type: str | None = None
    pay_band: str | None = None
    pay_schedule: str | None = None


class WageCheck(BaseModel):
    hourly_rate: Decimal | None
    minimum_rate: Decimal | None
    below_minimum: bool | None
    message: str
    source: str = "https://www.gov.uk/national-minimum-wage-rates"


class CompensationHistory(BaseModel):
    current: CompensationOut | None
    records: list[CompensationOut]
