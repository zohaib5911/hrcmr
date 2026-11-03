"""Tenant rota settings; archived settings remain available to historical shifts."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime, time  # noqa: TC003
from decimal import Decimal  # noqa: TC003

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
    column,
    false,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin


class ShiftType(Base, RecordMixin, TenantMixin):
    __tablename__ = "shift_types"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_shift_types_company_id_id"),
        Index(
            "uq_shift_types_live_name",
            "company_id",
            func.lower(column("name")),
            unique=True,
            postgresql_where=column("archived_at").is_(None),
        ),
        CheckConstraint("starts_at <> ends_at", name="duration"),
        CheckConstraint("(break_start is null) = (break_end is null)", name="break_pair"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    starts_at: Mapped[time] = mapped_column(Time, nullable=False)
    ends_at: Mapped[time] = mapped_column(Time, nullable=False)
    break_start: Mapped[time | None] = mapped_column(Time)
    break_end: Mapped[time | None] = mapped_column(Time)
    colour: Mapped[str] = mapped_column(String(7), nullable=False, server_default="#007aff")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def _scope_constraints(
    table: str,
) -> tuple[ForeignKeyConstraint, ForeignKeyConstraint, ForeignKeyConstraint, Index]:
    return (
        ForeignKeyConstraint(
            ["company_id", "department_id"],
            ["departments.company_id", "departments.id"],
            name=f"fk_{table}_department",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "department_id", "designation_id"],
            ["designations.company_id", "designations.department_id", "designations.id"],
            name=f"fk_{table}_designation",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "shift_type_id"],
            ["shift_types.company_id", "shift_types.id"],
            name=f"fk_{table}_shift",
            ondelete="RESTRICT",
        ),
        Index(
            f"uq_{table}_live_scope",
            "company_id",
            "department_id",
            "designation_id",
            "shift_type_id",
            unique=True,
            postgresql_where=column("archived_at").is_(None),
        ),
    )


class LatePolicy(Base, RecordMixin, TenantMixin):
    __tablename__ = "late_policies"
    __table_args__ = (
        *_scope_constraints("late_policies"),
        CheckConstraint(
            "grace_minutes between 0 and 1440 AND allowed_late_days_per_month between 0 and 31",
            name="limits",
        ),
        CheckConstraint(
            "deduction_value >= 0 AND ((deduction_type='none' AND deduction_value=0) "
            "OR deduction_type='fixed' OR (deduction_type='percentage_of_day' "
            "AND deduction_value<=100))",
            name="deduction",
        ),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    designation_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    shift_type_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    grace_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    allowed_late_days_per_month: Mapped[int] = mapped_column(Integer, nullable=False)
    deduction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    deduction_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DayOffPattern(Base, RecordMixin, TenantMixin):
    __tablename__ = "day_off_patterns"
    __table_args__ = (
        *_scope_constraints("day_off_patterns"),
        CheckConstraint(
            "weekdays_off <@ ARRAY[1,2,3,4,5,6,7] AND array_position(weekdays_off, NULL) IS NULL",
            name="weekdays",
        ),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    designation_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    shift_type_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    weekdays_off: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False)
    works_public_holidays: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
