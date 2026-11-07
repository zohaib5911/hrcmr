"""The dashboard and the set-up checklist (plan 8.2).

A card the caller may not read is left out of the response altogether."""

from __future__ import annotations

from pydantic import BaseModel


class EmployeesCardOut(BaseModel):
    active: int
    on_leave: int


class RtwCardOut(BaseModel):
    checked: int
    verified: int
    expiring: int
    expired: int
    evidence_missing: int
    not_recorded: int
    coverage_percent: int


class OffCardOut(BaseModel):
    count: int
    names: list[str]


class ApprovalsCardOut(BaseModel):
    pending: int


class DistributionRowOut(BaseModel):
    department: str
    headcount: int


class DistributionCardOut(BaseModel):
    rows: list[DistributionRowOut]


class LearningCardOut(BaseModel):
    overdue: int


class MyLearningCardOut(BaseModel):
    open: int
    overdue: int


class RecruitmentCardOut(BaseModel):
    latest: list[str]


class AttentionItemOut(BaseModel):
    label: str
    count: int
    link: str


class DashboardOut(BaseModel):
    first_name: str
    status_line: str
    needs_attention: list[AttentionItemOut]
    employees: EmployeesCardOut | None = None
    rtw: RtwCardOut | None = None
    off_today: OffCardOut | None = None
    approvals: ApprovalsCardOut | None = None
    distribution: DistributionCardOut | None = None
    learning: LearningCardOut | None = None
    my_learning: MyLearningCardOut | None = None
    recruitment: RecruitmentCardOut | None = None


class ChecklistItemOut(BaseModel):
    key: str
    label: str
    done: bool


class ChecklistOut(BaseModel):
    visible: bool
    done: int
    total: int
    items: list[ChecklistItemOut]
