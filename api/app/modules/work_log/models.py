"""Daily work descriptions with retained originals and audited soft removal."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime, time  # noqa: TC003
from decimal import Decimal  # noqa: TC003
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    Text,
    Time,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin


class WorkLogEntry(Base, RecordMixin, TenantMixin):
    __tablename__ = "work_log_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "employee_id"],
            ["employees.company_id", "employees.id"],
            name="fk_work_log_employee",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "employee_id", "responsibility_id"],
            [
                "employee_responsibilities.company_id",
                "employee_responsibilities.employee_id",
                "employee_responsibilities.id",
            ],
            name="fk_work_log_responsibility",
            ondelete="RESTRICT",
        ),
        CheckConstraint("from_time <> to_time AND hours>0 AND hours<=24", name="duration"),
        CheckConstraint("(removed_at is null) = (removed_by is null)", name="removed"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    from_time: Mapped[time] = mapped_column(Time, nullable=False)
    to_time: Mapped[time] = mapped_column(Time, nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    responsibility_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    responsibility_text: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    corrected_from: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
