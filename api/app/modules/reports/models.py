"""Durable report requests survive a missed Redis enqueue; artifacts remain private files."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin
from app.modules.reports.reference import REPORT_TYPES


class ReportJob(Base, RecordMixin, TenantMixin):
    __tablename__ = "report_jobs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "file_id"],
            ["files.company_id", "files.id"],
            name="fk_report_jobs_file",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "report_type in (" + ", ".join(repr(t) for t in REPORT_TYPES) + ")", name="report_type"
        ),
        CheckConstraint("status in ('queued','ready','failed')", name="status"),
        CheckConstraint("(status = 'ready') = (file_id is not null)", name="file_state"),
        CheckConstraint("(status = 'queued') = (finished_at is null)", name="finished_state"),
        CheckConstraint("(status = 'failed') = (error_code is not null)", name="error_state"),
        Index("ix_report_jobs_requester", "company_id", "requested_by", "created_at"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    report_type: Mapped[str] = mapped_column(String(40), nullable=False)
    requested_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="queued")
    file_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(40))
