"""Work log forms, private projections and reasoned administrative changes."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime, time  # noqa: TC003
from decimal import Decimal  # noqa: TC003
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.schemas import RequestModel


class WorkLogIn(RequestModel):
    date: date
    from_time: time
    to_time: time
    responsibility_id: uuid.UUID | None = None
    responsibility_text: str | None = Field(default=None, max_length=2000)
    description: str = Field(min_length=1, max_length=4000)

    @field_validator("responsibility_text", "description", mode="before")
    @classmethod
    def trim(cls, value: object) -> object:
        return value.strip() or None if isinstance(value, str) else value

    @field_validator("from_time", "to_time")
    @classmethod
    def clock(cls, value: time) -> time:
        if value.tzinfo is not None or value.second or value.microsecond:
            raise ValueError("Use local hours and minutes (HH:MM).")
        return value

    @model_validator(mode="after")
    def validate_entry(self) -> Self:
        if self.from_time == self.to_time:
            raise ValueError("Start and finish must differ.")
        if bool(self.responsibility_id) == bool(self.responsibility_text):
            raise ValueError("Choose a responsibility or enter one in your own words.")
        return self


class WorkLogEdit(WorkLogIn):
    revision: datetime


class WorkLogCorrect(WorkLogEdit):
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        return value.strip()


class WorkLogRemove(RequestModel):
    reason: str = Field(min_length=1, max_length=1000)
    revision: datetime

    @field_validator("reason", mode="before")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        return value.strip()


class WorkLogOut(BaseModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    date: date
    from_time: time
    to_time: time
    hours: Decimal
    responsibility_id: uuid.UUID | None
    responsibility_text: str
    description: str
    removed_at: datetime | None
    corrected_from: dict[str, Any] | None
    can_edit: bool
    revision: datetime


class WorkLogPage(BaseModel):
    items: list[WorkLogOut]
    total: int
    hours: Decimal
    employees: int
    next_offset: int | None
    timezone: str
    today: date


class OwnResponsibility(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    text: str
