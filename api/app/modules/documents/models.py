"""Company-wide documents retain their scanned files after archive."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin
from app.modules.documents.reference import CATEGORIES


class CompanyDocument(Base, RecordMixin, TenantMixin):
    __tablename__ = "company_documents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "file_id"],
            ["files.company_id", "files.id"],
            name="fk_company_documents_file",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "category in (" + ", ".join(repr(c) for c in CATEGORIES) + ")", name="category"
        ),
        CheckConstraint("length(trim(title)) > 0", name="title"),
        Index("ix_company_documents_review", "company_id", "next_review_date"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    file_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    next_review_date: Mapped[date | None] = mapped_column(Date)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
