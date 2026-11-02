"""The working pattern, bank holidays, holiday types and company holidays (plan.md section 6)."""

from __future__ import annotations

import uuid  # noqa: TC003  (SQLAlchemy resolves the Mapped[...] annotations at runtime)
from datetime import date, datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    column,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin

# The colours a holiday type can have: names, which the web app turns into its own palette.
HOLIDAY_COLOURS = ("blue", "green", "orange", "red", "gray")
REGIONS = ("england-and-wales", "scotland", "northern-ireland")


def _in(name: str, values: tuple[str, ...]) -> str:
    return f"{name} in ({', '.join(repr(v) for v in values)})"


class WorkingPatternDay(Base, RecordMixin, TenantMixin):
    """One weekday of the company's normal week (1 = Monday ... 7 = Sunday)."""

    __tablename__ = "working_pattern_days"
    __table_args__ = (
        CheckConstraint("weekday between 1 and 7", name="weekday"),
        CheckConstraint("hours >= 0 and hours <= 24", name="hours"),
        UniqueConstraint(
            "company_id", "weekday", name="uq_working_pattern_days_company_id_weekday"
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_working: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    hours: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False, server_default="0")


class BankHoliday(Base, RecordMixin):
    """A public holiday, by region. Not about one company: loaded weekly from GOV.UK."""

    __tablename__ = "bank_holidays"
    __table_args__ = (
        CheckConstraint(_in("region", REGIONS), name="region"),
        UniqueConstraint("region", "on_date", name="uq_bank_holidays_region_on_date"),
    )

    region: Mapped[str] = mapped_column(String(20), nullable=False)
    on_date: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class HolidayType(Base, RecordMixin, TenantMixin):
    __tablename__ = "holiday_types"
    __table_args__ = (
        CheckConstraint(_in("colour", HOLIDAY_COLOURS), name="colour"),
        Index(
            "uq_holiday_types_company_id_name",
            "company_id",
            func.lower(column("name")),
            unique=True,
            postgresql_where=column("archived_at").is_(None),
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    colour: Mapped[str] = mapped_column(String(10), nullable=False, server_default="blue")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CompanyHoliday(Base, RecordMixin, TenantMixin):
    """A closure: the company is shut from ``start_date`` to ``end_date`` (both included)."""

    __tablename__ = "company_holidays"
    __table_args__ = (CheckConstraint("end_date >= start_date", name="dates"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    holiday_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("holiday_types.id", ondelete="RESTRICT")
    )
    description: Mapped[str | None] = mapped_column(Text)
    # Whether these days come out of everyone's annual leave (the leave ledger applies it later).
    deduct_from_annual_leave: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
