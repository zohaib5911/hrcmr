"""Committed company leave-year closes retain the reviewed snapshot permanently."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin


class LeaveYearEndRun(Base, RecordMixin, TenantMixin):
    __tablename__ = "leave_year_end_runs"
    __table_args__ = (
        UniqueConstraint("company_id", "from_year", name="uq_leave_year_end_runs_company_year"),
        CheckConstraint("to_year > from_year", name="years"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    from_year: Mapped[date] = mapped_column(Date, nullable=False)
    to_year: Mapped[date] = mapped_column(Date, nullable=False)
    run_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    overrides: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    preview_token: Mapped[str] = mapped_column(String(64), nullable=False)
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
