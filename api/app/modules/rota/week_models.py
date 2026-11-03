"""Draft rota weeks and dated shifts; employees read the last published snapshot."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin


class RotaWeek(Base, RecordMixin, TenantMixin):
    __tablename__ = "rota_weeks"
    __table_args__ = (
        UniqueConstraint("company_id", "week_start", name="uq_rota_week_start"),
        UniqueConstraint("company_id", "id", name="uq_rota_weeks_company_id_id"),
        CheckConstraint("extract(isodow from week_start)=1", name="monday"),
        CheckConstraint("status in ('draft','published') AND version>=0", name="state"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    published_shifts: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )


class ScheduledShift(Base, RecordMixin, TenantMixin):
    __tablename__ = "scheduled_shifts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "rota_week_id"],
            ["rota_weeks.company_id", "rota_weeks.id"],
            name="fk_scheduled_shift_week",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "employee_id"],
            ["employees.company_id", "employees.id"],
            name="fk_scheduled_shift_employee",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "shift_type_id"],
            ["shift_types.company_id", "shift_types.id"],
            name="fk_scheduled_shift_type",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "ends_at > starts_at AND unpaid_break_minutes >= 0 AND "
            "unpaid_break_minutes * interval '1 minute' <= ends_at-starts_at",
            name="duration",
        ),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    rota_week_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    unpaid_break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    shift_type_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    note: Mapped[str | None] = mapped_column(Text)
