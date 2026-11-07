"""Requisition inputs and outputs (plan 8.11)."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.core.schemas import RequestModel

Title = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200, pattern=r"^[^\r\n]+$"),
]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
BudgetPer = Literal["year", "month", "hour"]
RequisitionStatus = Literal["draft", "open", "on_hold", "filled", "cancelled"]


class RequisitionIn(RequestModel):
    job_title: Title
    department_id: uuid.UUID | None = None
    headcount: int = Field(default=1, ge=1, le=999)
    grade: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    budget_from: Money | None = None
    budget_to: Money | None = None
    budget_per: BudgetPer | None = None
    justification: Annotated[str, StringConstraints(max_length=5000)] | None = None

    @model_validator(mode="after")
    def budget_order(self) -> Self:
        if (
            self.budget_from is not None
            and self.budget_to is not None
            and (self.budget_from > self.budget_to)
        ):
            raise ValueError("The budget from must not be more than the budget to.")
        return self


class RequisitionStatusIn(RequestModel):
    status: RequisitionStatus


class RequisitionOut(BaseModel):
    id: uuid.UUID
    job_title: str
    department_id: uuid.UUID | None
    department: str | None
    headcount: int
    grade: str | None
    budget_from: Decimal | None
    budget_to: Decimal | None
    budget_per: BudgetPer | None
    justification: str | None
    status: RequisitionStatus
    approved_at: datetime | None
    approved_by_name: str | None
    created_at: datetime
    updated_at: datetime


class RequisitionPage(BaseModel):
    items: list[RequisitionOut]
    total: int


class RecruitmentSummary(BaseModel):
    open_requisitions: int
    requisitions: int
    live_postings: int
    postings: int
    candidates: int
    applications_in_progress: int
