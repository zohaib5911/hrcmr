"""Requisitions, postings, candidates, applications, interviews and offers (plan 6.8)."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin

BUDGET_PERIODS = "('year','month','hour')"


class Requisition(Base, RecordMixin, TenantMixin):
    __tablename__ = "requisitions"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_requisitions_company_id_id"),
        CheckConstraint("length(trim(job_title)) > 0", name="job_title"),
        CheckConstraint("headcount between 1 and 999", name="headcount"),
        CheckConstraint("status in ('draft','open','on_hold','filled','cancelled')", name="status"),
        CheckConstraint(f"budget_per is null or budget_per in {BUDGET_PERIODS}", name="budget_per"),
        CheckConstraint(
            "budget_from is null or budget_to is null or budget_from <= budget_to",
            name="budget_range",
        ),
        CheckConstraint("(approved_by is null) = (approved_at is null)", name="approval_stamp"),
        CheckConstraint(
            "status not in ('open','filled') or approved_at is not null",
            name="approved_before_open",
        ),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    job_title: Mapped[str] = mapped_column(String(200), nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("departments.id", ondelete="RESTRICT")
    )
    headcount: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    grade: Mapped[str | None] = mapped_column(String(40))
    budget_from: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    budget_to: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    budget_per: Mapped[str | None] = mapped_column(String(6))
    justification: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="draft")
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Posting(Base, RecordMixin, TenantMixin):
    __tablename__ = "postings"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_postings_company_id_id"),
        UniqueConstraint("company_id", "slug", name="uq_postings_slug"),
        CheckConstraint("length(trim(title)) > 0", name="title"),
        CheckConstraint("visibility in ('internal','external')", name="visibility"),
        CheckConstraint("vacancies between 1 and 999", name="vacancies"),
        CheckConstraint("status in ('draft','open','closed')", name="status"),
        CheckConstraint(
            "visa_sponsorship in ('not_stated','available','considered','not_available')",
            name="visa_sponsorship",
        ),
        CheckConstraint(f"salary_per is null or salary_per in {BUDGET_PERIODS}", name="salary_per"),
        CheckConstraint(
            "salary_from is null or salary_to is null or salary_from <= salary_to",
            name="salary_range",
        ),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    requisition_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("requisitions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    visibility: Mapped[str] = mapped_column(String(8), nullable=False, server_default="internal")
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("locations.id", ondelete="RESTRICT")
    )
    job_code: Mapped[str | None] = mapped_column(String(40))
    soc_code: Mapped[str | None] = mapped_column(String(10))
    vacancies: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    posted_on: Mapped[date | None] = mapped_column(Date)
    closes_on: Mapped[date | None] = mapped_column(Date)
    contact_email: Mapped[str | None] = mapped_column(String(254))
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    salary_from: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    salary_to: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    salary_per: Mapped[str | None] = mapped_column(String(6))
    weekly_hours: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    description: Mapped[str | None] = mapped_column(Text)
    visa_sponsorship: Mapped[str] = mapped_column(
        String(14), nullable=False, server_default="not_stated"
    )
    status: Mapped[str] = mapped_column(String(6), nullable=False, server_default="draft")


class Candidate(Base, RecordMixin, TenantMixin):
    __tablename__ = "candidates"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_candidates_company_id_id"),
        CheckConstraint("length(trim(first_name)) > 0", name="first_name"),
        CheckConstraint("length(trim(last_name)) > 0", name="last_name"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(40))
    source: Mapped[str | None] = mapped_column(String(40))
    cv_file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("files.id", ondelete="RESTRICT")
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Application(Base, RecordMixin, TenantMixin):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_applications_company_id_id"),
        UniqueConstraint(
            "company_id", "candidate_id", "posting_id", name="uq_applications_candidate_posting"
        ),
        CheckConstraint(
            "stage in ('applied','shortlisted','interview','offer_letter','offer_accepted',"
            "'hired','rejected','withdrawn')",
            name="stage",
        ),
        CheckConstraint("applied_via in ('admin','careers_page')", name="applied_via"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("candidates.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    posting_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("postings.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(String(16), nullable=False, server_default="applied")
    stage_history: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    cover_note: Mapped[str | None] = mapped_column(Text)
    applied_via: Mapped[str] = mapped_column(String(14), nullable=False, server_default="admin")


class Interview(Base, RecordMixin, TenantMixin):
    __tablename__ = "interviews"
    __table_args__ = (
        CheckConstraint("duration_minutes between 5 and 480", name="duration"),
        CheckConstraint("mode in ('in_person','video','phone')", name="mode"),
        CheckConstraint("outcome in ('pending','passed','failed','no_show')", name="outcome"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("applications.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="60")
    mode: Mapped[str] = mapped_column(String(10), nullable=False)
    location_or_link: Mapped[str | None] = mapped_column(String(300))
    interviewer_employee_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(Uuid), nullable=False, server_default="{}"
    )
    outcome: Mapped[str] = mapped_column(String(10), nullable=False, server_default="pending")
    notes: Mapped[str | None] = mapped_column(Text)


class Offer(Base, RecordMixin, TenantMixin):
    __tablename__ = "offers"
    __table_args__ = (
        CheckConstraint("length(trim(role_title)) > 0", name="role_title"),
        CheckConstraint(f"salary_per in {BUDGET_PERIODS}", name="salary_per"),
        CheckConstraint(
            "status in ('draft','sent','accepted','declined','withdrawn')", name="status"
        ),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("applications.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    role_title: Mapped[str] = mapped_column(String(200), nullable=False)
    salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    salary_per: Mapped[str] = mapped_column(String(6), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="draft")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
