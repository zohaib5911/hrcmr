"""The compliance hub's action links, counts and dated inspection checklist."""

from __future__ import annotations

from datetime import date  # noqa: TC003
from typing import Literal

from pydantic import BaseModel

ActivityCategory = Literal["all", "rtw", "employees", "attendance", "documents", "changes"]


class AttentionItem(BaseModel):
    id: str
    priority: int
    title: str
    detail: str
    action: str
    href: str
    due_on: date | None


class CoverageCount(BaseModel):
    status: str
    label: str
    count: int
    href: str


class Coverage(BaseModel):
    valid: int
    total: int
    counts: list[CoverageCount]


class ReadinessCheck(BaseModel):
    id: str
    title: str
    status: Literal["complete", "incomplete", "not_applicable"]
    detail: str
    href: str


class ExpiringItem(BaseModel):
    id: str
    employee_name: str
    document_type: str
    document_label: str
    expires_on: date
    days_left: int
    bucket: Literal["overdue", "next_30", "31_60", "61_90"]
    href: str


class ComplianceOverview(BaseModel):
    today: date
    attention: list[AttentionItem]
    coverage: Coverage
    readiness: list[ReadinessCheck]
    expiring: list[ExpiringItem]
