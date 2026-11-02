"""Employee sponsor evidence with encrypted references and retained document versions (T7.2)."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    column,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin
from app.db.types import EncryptedString

CONDITIONS = {
    "doc_type": "doc_type in ('visa', 'passport', 'dbs', 'euss', 'national_id', 'other')",
    "version": "version > 0",
    "visa_route": (
        "visa_route is null or visa_route in ('skilled_worker', 'health_care_worker', "
        "'global_business_mobility', 'scale_up', 'temporary_worker', 'graduate', 'student', "
        "'euss_settled', 'euss_pre_settled', 'family', 'other')"
    ),
    "visa_fields": (
        "(doc_type = 'visa' and visa_route is not null) or (doc_type <> 'visa' and "
        "visa_route is null and cos_number is null and soc_code is null "
        "and sponsored_salary is null)"
    ),
    "salary": "sponsored_salary is null or sponsored_salary >= 0",
    "soc": "soc_code is null or soc_code ~ '^[0-9]{4}$'",
    "country": "issuing_country is null or issuing_country ~ '^[A-Z]{2}$'",
    "dates": "issue_date is null or expiry_date is null or expiry_date >= issue_date",
    "withdrawal": (
        "(withdrawn_at is null and withdraw_reason is null) or (withdrawn_at is not null "
        "and withdraw_reason is not null and length(trim(withdraw_reason)) > 0 "
        "and superseded_by is null)"
    ),
    "renewal": "renewal_date is not null or renewal_notes is null",
}


class SponsorDocument(Base, RecordMixin, TenantMixin):
    __tablename__ = "sponsor_documents"
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False
    )
    doc_type: Mapped[str] = mapped_column(String(11), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(
        EncryptedString("sponsor_documents.reference_number")
    )
    issuing_country: Mapped[str | None] = mapped_column(String(2))
    visa_route: Mapped[str | None] = mapped_column(String(24))
    cos_number: Mapped[str | None] = mapped_column(EncryptedString("sponsor_documents.cos_number"))
    soc_code: Mapped[str | None] = mapped_column(String(4))
    sponsored_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    review_date: Mapped[date | None] = mapped_column(Date)
    evidence_file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("files.id", ondelete="RESTRICT")
    )
    remarks: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "sponsor_documents.id", ondelete="RESTRICT", deferrable=True, initially="DEFERRED"
        ),
    )
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdraw_reason: Mapped[str | None] = mapped_column(Text)
    renewal_date: Mapped[date | None] = mapped_column(Date)
    renewal_notes: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        UniqueConstraint("company_id", "employee_id", "doc_type", "version"),
        Index(
            "uq_sponsor_documents_current",
            "company_id",
            "employee_id",
            "doc_type",
            unique=True,
            postgresql_where=column("superseded_by").is_(None) & column("withdrawn_at").is_(None),
        ),
        Index("ix_sponsor_documents_employee", "company_id", "employee_id"),
        *(CheckConstraint(sql, name=name) for name, sql in CONDITIONS.items()),
    )
