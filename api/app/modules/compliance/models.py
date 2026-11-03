"""Change-of-circumstances snapshots and organisation reporting records (T7.3)."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin

REGION_CHECK = "calendar_region in ('england-and-wales', 'scotland', 'northern-ireland')"
REPORT_CHECK = (
    "(reported_at is null and reported_by_user_id is null and reported_reference is null "
    "and report_recorded_at is null) or (reported_at is not null "
    "and reported_by_user_id is not null "
    "and reported_reference is not null and length(trim(reported_reference)) > 0 "
    "and report_recorded_at is not null)"
)
EMPLOYEE_TYPES_CHECK = (
    "change_type in ('did_not_start', 'unauthorised_absence', 'sponsorship_stopped', "
    "'salary_reduced', 'job_or_soc_changed', 'work_location_changed', "
    "'working_hours_changed', 'unpaid_reduced_absence', 'other')"
)
ORG_TYPES_CHECK = (
    "change_type in ('address', 'ownership', 'name', 'key_personnel', 'ao_or_key_contact', 'other')"
)


class ReportingMixin:
    change_date: Mapped[date] = mapped_column(Date, nullable=False)
    calendar_region: Mapped[str] = mapped_column(String(20), nullable=False)
    calendar_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    calendar_holidays: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reported_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT")
    )
    reported_reference: Mapped[str | None] = mapped_column(String(160))
    report_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    remarks: Mapped[str | None] = mapped_column(Text)


class ChangeOfCircumstances(Base, RecordMixin, ReportingMixin, TenantMixin):
    __tablename__ = "change_of_circumstances"
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False
    )
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)
    deadline_date: Mapped[date] = mapped_column(Date, nullable=False)
    employment_type: Mapped[str | None] = mapped_column(String(12))
    job_title: Mapped[str | None] = mapped_column(String(160))
    nationality: Mapped[str | None] = mapped_column(String(80))
    contact_number: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str | None] = mapped_column(Text)
    ack_inform_hr: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    ack_home_office_interview: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    documents_snapshot: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    __table_args__ = (
        CheckConstraint(EMPLOYEE_TYPES_CHECK, name="change_type"),
        CheckConstraint("deadline_date > change_date", name="deadline"),
        CheckConstraint("calendar_checked_at is not null", name="calendar_checked"),
        CheckConstraint(REGION_CHECK, name="region"),
        CheckConstraint(REPORT_CHECK, name="report"),
        Index("ix_change_of_circumstances_employee", "company_id", "employee_id"),
        Index("ix_change_of_circumstances_deadline", "company_id", "deadline_date"),
    )


class OrgChange(Base, RecordMixin, ReportingMixin, TenantMixin):
    __tablename__ = "org_changes"
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    change_type: Mapped[str] = mapped_column(String(20), nullable=False)
    deadline_date: Mapped[date | None] = mapped_column(Date)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archive_reason: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint(ORG_TYPES_CHECK, name="change_type"),
        CheckConstraint(
            "(change_type = 'ao_or_key_contact' and deadline_date is null) or "
            "(change_type <> 'ao_or_key_contact' and deadline_date is not null "
            "and deadline_date > change_date and calendar_checked_at is not null)",
            name="deadline",
        ),
        CheckConstraint(
            "(archived_at is null and archive_reason is null) or (archived_at is not null "
            "and archive_reason is not null and length(trim(archive_reason)) > 0 "
            "and reported_at is null)",
            name="archive",
        ),
        CheckConstraint(REGION_CHECK, name="region"),
        CheckConstraint(REPORT_CHECK, name="report"),
        Index("ix_org_changes_deadline", "company_id", "deadline_date"),
    )
