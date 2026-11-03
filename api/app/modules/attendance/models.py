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
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin


class AttendanceRecord(Base, RecordMixin, TenantMixin):
    __tablename__ = "attendance_records"
    __table_args__ = (
        Index(
            "uq_attendance_open_clock",
            "company_id",
            "employee_id",
            unique=True,
            postgresql_where=text("source='clock' and clock_in is not null and clock_out is null"),
        ),
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


class AttendanceImport(Base, RecordMixin, TenantMixin):
    __tablename__ = "attendance_imports"
    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "file_id"],
            ["files.company_id", "files.id"],
            name="fk_attendance_imports_company_file",
            ondelete="RESTRICT",
        ),
        CheckConstraint("status in ('previewed','committed')", name="status"),
        CheckConstraint(
            "rows_total > 0 AND rows_valid >= 0 AND rows_valid <= rows_total", name="rows"
        ),
        CheckConstraint(
            "(from_date is null and to_date is null) or "
            "(from_date is not null and to_date is not null and to_date >= from_date)",
            name="dates",
        ),
        CheckConstraint(
            "(status='previewed' and committed_at is null) or "
            "(status='committed' and committed_at is not null)",
            name="committed",
        ),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    file_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    from_date: Mapped[date | None] = mapped_column(Date)
    to_date: Mapped[date | None] = mapped_column(Date)
    rows_total: Mapped[int] = mapped_column(Integer, nullable=False)
    rows_valid: Mapped[int] = mapped_column(Integer, nullable=False)
    rows: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="previewed")
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TimesheetApproval(Base, RecordMixin, TenantMixin):
    """One current weekly approval; the audit trail retains every prior decision."""

    __tablename__ = "timesheet_approvals"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "employee_id", "period_start", name="uq_timesheet_employee_week"
        ),
        ForeignKeyConstraint(
            ["company_id", "employee_id"],
            ["employees.company_id", "employees.id"],
            name="fk_timesheet_company_employee",
            ondelete="RESTRICT",
        ),
        CheckConstraint("period_end = period_start + 6", name="period"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
