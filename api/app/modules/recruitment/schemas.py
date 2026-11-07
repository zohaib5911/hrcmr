"""Requisition inputs and outputs (plan 8.11)."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, EmailStr, Field, StringConstraints, model_validator

from app.core.schemas import RequestModel
from app.modules.rtw.schemas import RTWStatus  # noqa: TC001 (pydantic reads it at run time)

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


PostingVisibility = Literal["internal", "external"]
VisaSponsorship = Literal["not_stated", "available", "considered", "not_available"]
PostingStatus = Literal["draft", "open", "closed"]
SocCode = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9]{4}$")]


class PostingIn(RequestModel):
    requisition_id: uuid.UUID
    title: Title
    visibility: PostingVisibility = "internal"
    location_id: uuid.UUID | None = None
    job_code: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    soc_code: SocCode | None = None
    vacancies: int = Field(default=1, ge=1, le=999)
    posted_on: date | None = None
    closes_on: date | None = None
    contact_email: EmailStr | None = None
    contact_phone: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None
    ) = None
    salary_from: Money | None = None
    salary_to: Money | None = None
    salary_per: BudgetPer | None = None
    weekly_hours: Decimal | None = Field(default=None, ge=0, le=168, max_digits=4, decimal_places=1)
    description: Annotated[str, StringConstraints(max_length=20000)] | None = None
    visa_sponsorship: VisaSponsorship = "not_stated"

    @model_validator(mode="after")
    def dates_and_pay(self) -> Self:
        if self.posted_on and self.closes_on and self.closes_on < self.posted_on:
            raise ValueError("The closing date must be on or after the posted date.")
        if (
            self.salary_from is not None
            and self.salary_to is not None
            and (self.salary_from > self.salary_to)
        ):
            raise ValueError("The salary from must not be more than the salary to.")
        return self


class PostingStatusIn(RequestModel):
    status: PostingStatus


class PostingOut(BaseModel):
    id: uuid.UUID
    requisition_id: uuid.UUID
    requisition_title: str
    title: str
    slug: str
    visibility: PostingVisibility
    location_id: uuid.UUID | None
    location: str | None
    job_code: str | None
    soc_code: str | None
    vacancies: int
    posted_on: date | None
    closes_on: date | None
    contact_email: str | None
    contact_phone: str | None
    salary_from: Decimal | None
    salary_to: Decimal | None
    salary_per: BudgetPer | None
    weekly_hours: Decimal | None
    description: str | None
    visa_sponsorship: VisaSponsorship
    status: PostingStatus
    public_link: str | None
    created_at: datetime
    updated_at: datetime


class PostingPage(BaseModel):
    items: list[PostingOut]
    total: int


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class CandidateIn(RequestModel):
    first_name: Name
    last_name: Name
    email: EmailStr | None = None
    phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    source: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None


class CandidateOut(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    source: str | None
    archived: bool
    rtw_status: RTWStatus
    created_at: datetime
    updated_at: datetime


class CandidatePage(BaseModel):
    items: list[CandidateOut]
    total: int


class CandidateFile(BaseModel):
    id: uuid.UUID
    name: str
    mime: str
    size: int
    scan_status: str
    created_at: datetime


Stage = Literal[
    "applied",
    "shortlisted",
    "interview",
    "offer_letter",
    "offer_accepted",
    "hired",
    "rejected",
    "withdrawn",
]


class ApplicationIn(RequestModel):
    candidate_id: uuid.UUID
    posting_id: uuid.UUID
    cover_note: Annotated[str, StringConstraints(max_length=5000)] | None = None


class ApplicationStageIn(RequestModel):
    stage: Stage


class StageEntry(BaseModel):
    stage: Stage
    at: datetime
    by: uuid.UUID | None


class ApplicationOut(BaseModel):
    id: uuid.UUID
    candidate_id: uuid.UUID
    candidate_name: str
    posting_id: uuid.UUID
    posting_title: str
    stage: Stage
    stage_label: str
    stage_history: list[StageEntry]
    cover_note: str | None
    applied_via: Literal["admin", "careers_page"]
    candidate_rtw_status: RTWStatus
    created_at: datetime
    updated_at: datetime


class ApplicationPage(BaseModel):
    items: list[ApplicationOut]
    total: int


class PipelineStage(BaseModel):
    stage: Stage
    label: str
    count: int


class Pipeline(BaseModel):
    stages: list[PipelineStage]
    total: int


InterviewMode = Literal["in_person", "video", "phone"]
InterviewOutcome = Literal["pending", "passed", "failed", "no_show"]


class InterviewIn(RequestModel):
    scheduled_at: datetime
    duration_minutes: int = Field(default=60, ge=5, le=480)
    mode: InterviewMode
    location_or_link: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None
    ) = None
    interviewer_employee_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)
    notes: Annotated[str, StringConstraints(max_length=5000)] | None = None

    @model_validator(mode="after")
    def has_time_zone(self) -> Self:
        if self.scheduled_at.tzinfo is None:
            raise ValueError("Give the date and time with a time zone.")
        return self


class InterviewPatch(RequestModel):
    outcome: InterviewOutcome | None = None
    notes: Annotated[str, StringConstraints(max_length=5000)] | None = None


class InterviewerOut(BaseModel):
    id: uuid.UUID
    name: str


class InterviewOut(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    scheduled_at: datetime
    duration_minutes: int
    mode: InterviewMode
    location_or_link: str | None
    interviewers: list[InterviewerOut]
    outcome: InterviewOutcome
    notes: str | None
    created_at: datetime
    updated_at: datetime


OfferStatus = Literal["draft", "sent", "accepted", "declined", "withdrawn"]


class OfferIn(RequestModel):
    role_title: Title
    salary: Money
    salary_per: BudgetPer
    start_date: date | None = None


class OfferPatch(RequestModel):
    status: OfferStatus | None = None
    role_title: Title | None = None
    salary: Money | None = None
    salary_per: BudgetPer | None = None
    start_date: date | None = None


class OfferOut(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    role_title: str
    salary: Decimal
    salary_per: BudgetPer
    start_date: date | None
    status: OfferStatus
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ConvertIn(RequestModel):
    employee_number: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
    ]
    hire_date: date | None = None
    status: Literal["active", "on_leave"] = "active"
    phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None


class ConvertOut(BaseModel):
    employee_id: uuid.UUID
    application: ApplicationOut
