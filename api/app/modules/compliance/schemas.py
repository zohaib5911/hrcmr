"""Change log snapshots and reporting inputs; clients never supply their own deadline."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.schemas import RequestModel
from app.modules.sponsor_documents.schemas import SponsorDocumentOut  # noqa: TC001

ChangeType = Literal[
    "did_not_start",
    "unauthorised_absence",
    "sponsorship_stopped",
    "salary_reduced",
    "job_or_soc_changed",
    "work_location_changed",
    "working_hours_changed",
    "unpaid_reduced_absence",
    "other",
]
OrgChangeType = Literal[
    "address", "ownership", "name", "key_personnel", "ao_or_key_contact", "other"
]
ChangeState = Literal["unreported", "overdue", "reported", "prompt"]
FilterState = Literal["all", "unreported", "overdue"]
EmploymentType = Literal[
    "full_time", "part_time", "fixed_term", "zero_hours", "casual", "apprentice", "agency"
]


class SnapshotIn(RequestModel):
    employment_type: EmploymentType | None = None
    job_title: str | None = Field(default=None, max_length=160)
    nationality: str | None = Field(default=None, max_length=80)
    contact_number: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=2000)

    @field_validator("*", mode="before")
    @classmethod
    def trim(cls, value: object) -> object:
        return value.strip() or None if isinstance(value, str) else value


class ChangeIn(SnapshotIn):
    change_type: ChangeType
    change_date: date
    remarks: str | None = Field(default=None, max_length=2000)
    ack_inform_hr: bool = False
    ack_home_office_interview: bool = False
    documents_snapshot: list[uuid.UUID] = Field(default_factory=list, max_length=50)


class OrgChangeIn(RequestModel):
    change_type: OrgChangeType
    change_date: date = Field(description="The date the organisation became aware of the change.")
    remarks: str | None = Field(default=None, max_length=2000)

    @field_validator("remarks", mode="before")
    @classmethod
    def trim(cls, value: object) -> object:
        return value.strip() or None if isinstance(value, str) else value


class ReportedIn(RequestModel):
    reported_date: date
    reference: str = Field(min_length=1, max_length=160)

    @field_validator("reference", mode="before")
    @classmethod
    def trim(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ArchiveChangeIn(RequestModel):
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def trim(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ReportingOut(BaseModel):
    id: uuid.UUID
    change_date: date
    deadline_date: date | None
    calendar_region: str
    calendar_checked_at: datetime | None
    calendar_holidays: list[date]
    remarks: str | None
    status: ChangeState
    working_days_left: int | None
    reported_at: datetime | None
    reported_date: date | None
    reported_by_user_id: uuid.UUID | None
    reporter_name: str | None
    reported_reference: str | None
    report_recorded_at: datetime | None
    reported_on_time: bool | None
    created_at: datetime


class ChangeOut(ReportingOut):
    change_type: ChangeType
    employee_id: uuid.UUID
    employee_number: str
    employee_name: str
    employment_type: str | None
    job_title: str | None
    nationality: str | None
    contact_number: str | None
    address: str | None
    ack_inform_hr: bool
    ack_home_office_interview: bool
    documents_snapshot: list[uuid.UUID]


class OrgChangeOut(ReportingOut):
    change_type: OrgChangeType
    archived_at: datetime | None
    archive_reason: str | None


class ChangeDefaults(SnapshotIn):
    documents: list[SponsorDocumentOut]


class DeadlineOut(BaseModel):
    deadline_date: date | None
    calendar_region: str
    calendar_checked_at: datetime | None
    bank_holidays_excluded: list[date]
