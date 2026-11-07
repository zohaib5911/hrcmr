"""Org chart and hierarchy level shapes (plan 8.13)."""

from __future__ import annotations

import uuid  # noqa: TC003
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.core.schemas import RequestModel

LevelName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class LevelIn(RequestModel):
    name: LevelName
    rank: int | None = Field(default=None, ge=1, le=1000)


class LevelPatch(RequestModel):
    name: LevelName | None = None
    rank: int | None = Field(default=None, ge=1, le=1000)


class LevelOut(BaseModel):
    id: uuid.UUID
    name: str
    rank: int


class OrgPerson(BaseModel):
    id: uuid.UUID
    name: str
    job_title: str | None
    department: str | None
    level: str | None
    rtw_status: str | None  # only filled when the caller may read RTW (employee.rtw.read)
    reports: list[OrgPerson]


class OrgChartOut(BaseModel):
    rtw_visible: bool
    unassigned: list[OrgPerson]  # people without a Reporting Authority; each carries their reports
