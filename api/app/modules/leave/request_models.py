"""Leave requests retain reviewed quantities and dated working-day snapshots."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin


class LeaveRequest(Base, RecordMixin, TenantMixin):
    __tablename__ = "leave_requests"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_leave_requests_company_id_id"),
        ForeignKeyConstraint(
            ["company_id", "employee_id"],
            ["employees.company_id", "employees.id"],
            name="fk_leave_requests_company_employee",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "leave_type_id"],
            ["leave_types.company_id", "leave_types.id"],
            name="fk_leave_requests_company_type",
            ondelete="RESTRICT",
        ),
        CheckConstraint("end_date >= start_date AND end_date - start_date <= 366", name="dates"),
        CheckConstraint("status in ('pending','approved','rejected','cancelled')", name="status"),
        CheckConstraint("working_days > 0", name="working_days"),
        Index(
            "ix_leave_requests_employee_dates",
            "company_id",
            "employee_id",
            "start_date",
            "end_date",
        ),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    leave_type_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    half_day_start: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    half_day_end: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    working_days: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    working_dates: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="pending")
    decided_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
