"""Employment tab inputs and history (plan 8.3)."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date  # noqa: TC003
from decimal import Decimal  # noqa: TC003
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.schemas import RequestModel


class HireDateIn(RequestModel):
    hire_date: date
    reason: str = Field(min_length=1, max_length=1000)


class AssignmentIn(RequestModel):
    department_id: uuid.UUID | None = None
    designation_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    reporting_authority_employee_id: uuid.UUID | None = None
    leave_sanctioning_employee_id: uuid.UUID | None = None
    organogram_level_id: uuid.UUID | None = None
    employment_type: Literal[
        "full_time", "part_time", "fixed_term", "zero_hours", "casual", "apprentice", "agency"
    ]
    custom_working_days: list[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]] | None = (
        Field(default=None, min_length=1, max_length=7)
    )
    hours_per_day: Decimal | None = Field(default=None, gt=0, le=24, decimal_places=2)
    effective_from: date

    @model_validator(mode="after")
    def unique_days(self) -> Self:
        if self.custom_working_days and len(set(self.custom_working_days)) != len(
            self.custom_working_days
        ):
            raise ValueError("Choose each day only once.")
        return self


class AssignmentOut(AssignmentIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    ended_at: date | None


class ResponsibilityIn(RequestModel):
    text: str = Field(min_length=1, max_length=5000)
    sort: int = Field(default=0, ge=0)


class ResponsibilityOut(ResponsibilityIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class PreviousEmploymentIn(RequestModel):
    job_title: str | None = Field(default=None, max_length=120)
    started_on: date | None = None
    left_on: date | None = None
    total_experience_years: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=1)
    description: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def dates(self) -> Self:
        if self.started_on and self.left_on and self.left_on < self.started_on:
            raise ValueError("The leaving date must be on or after the start date.")
        return self


class PreviousEmploymentOut(PreviousEmploymentIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class EducationIn(RequestModel):
    qualification: str = Field(min_length=1, max_length=120)
    subject: str | None = Field(default=None, max_length=120)
    institution: str | None = Field(default=None, max_length=120)
    awarding_body: str | None = Field(default=None, max_length=120)
    year: int | None = Field(default=None, ge=1900, le=2200)
    percentage: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=2)
    grade: str | None = Field(default=None, max_length=40)


class EducationOut(EducationIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class TrainingIn(RequestModel):
    title: str = Field(min_length=1, max_length=160)
    started_on: date | None = None
    ended_on: date | None = None
    description: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def dates(self) -> Self:
        if self.started_on and self.ended_on and self.ended_on < self.started_on:
            raise ValueError("The end date must be on or after the start date.")
        return self


class TrainingOut(TrainingIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class MembershipIn(RequestModel):
    licence_title: str = Field(min_length=1, max_length=160)
    licence_number: str | None = Field(default=None, max_length=80)
    started_on: date | None = None
    ended_on: date | None = None

    @model_validator(mode="after")
    def dates(self) -> Self:
        if self.started_on and self.ended_on and self.ended_on < self.started_on:
            raise ValueError("The end date must be on or after the start date.")
        return self


class MembershipOut(MembershipIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class EmploymentTab(BaseModel):
    hire_date: date
    assignments: list[AssignmentOut]
    responsibilities: list[ResponsibilityOut]
    previous_employment: PreviousEmploymentOut | None
    education: list[EducationOut]
    training: list[TrainingOut]
    memberships: list[MembershipOut]
