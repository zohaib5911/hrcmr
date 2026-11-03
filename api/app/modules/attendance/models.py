"""Attendance records, first written by approved leave (T8.3); workspace in T9.1."""

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
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin


class AttendanceRecord(Base, RecordMixin, TenantMixin):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "employee_id", "date", name="uq_attendance_records_company_employee_date"
        ),
        ForeignKeyConstraint(
            ["company_id", "employee_id"],
            ["employees.company_id", "employees.id"],
            name="fk_attendance_records_company_employee",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "leave_request_id"],
            ["leave_requests.company_id", "leave_requests.id"],
            name="fk_attendance_records_company_leave",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status in ('present','absent','late','half_day','on_leave','sick')", name="status"
        ),
        CheckConstraint("source in ('manual','import','grid','clock','leave_sync')", name="source"),
        CheckConstraint(
            "unpaid_break_minutes >= 0 AND (hours IS NULL OR hours >= 0)", name="hours"
        ),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    clock_in: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    clock_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unpaid_break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    hours: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(12), nullable=False, server_default="manual")
    geo: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    leave_request_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
