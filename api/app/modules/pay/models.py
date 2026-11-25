"""Pay settings (plan.md section 6): bank accounts, tax codes, payment types, pay bands and pay
schedules. Every row is the company's own; none is deleted, only archived."""

from __future__ import annotations

import uuid  # noqa: TC003  (SQLAlchemy resolves the Mapped[...] annotations at runtime)
from datetime import datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Uuid,
    column,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin
from app.db.types import EncryptedString

FREQUENCIES = ("weekly", "fortnightly", "four_weekly", "monthly")
PAY_DAY_KINDS = ("weekday", "day_of_month", "last_day", "last_working_day")


def _company() -> Mapped[uuid.UUID]:
    return mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )


def _unique_name(table: str, name: str) -> Index:
    """One live row per name (ignoring case) in a company; an archived row frees its name."""
    return Index(
        f"uq_{table}_company_id_{name}",
        "company_id",
        func.lower(column(name)),
        unique=True,
        postgresql_where=column("archived_at").is_(None),
    )


class BankAccount(Base, RecordMixin, TenantMixin):
    """A company bank account. The sort code and account number are stored encrypted and are only
    ever shown masked."""

    __tablename__ = "company_bank_accounts"

    company_id: Mapped[uuid.UUID] = _company()
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_holder: Mapped[str] = mapped_column(String(120), nullable=False)
    sort_code: Mapped[str] = mapped_column(
        EncryptedString("company_bank_accounts.sort_code"), nullable=False
    )
    account_number: Mapped[str] = mapped_column(
        EncryptedString("company_bank_accounts.account_number"), nullable=False
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # At most one live main account per company (ISS-27).
    __table_args__ = (
        Index(
            "uq_company_bank_accounts_one_primary",
            "company_id",
            unique=True,
            postgresql_where=column("is_primary").is_(True) & column("archived_at").is_(None),
        ),
    )


class TaxCode(Base, RecordMixin, TenantMixin):
    __tablename__ = "tax_codes"
    __table_args__ = (
        CheckConstraint("deduction_percentage between 0 and 100", name="deduction_percentage"),
        _unique_name("tax_codes", "code"),
    )

    company_id: Mapped[uuid.UUID] = _company()
    code: Mapped[str] = mapped_column(String(12), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(80))
    deduction_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PaymentType(Base, RecordMixin, TenantMixin):
    __tablename__ = "payment_types"
    __table_args__ = (
        CheckConstraint("min_hourly_rate >= 0", name="min_hourly_rate"),
        _unique_name("payment_types", "name"),
    )

    company_id: Mapped[uuid.UUID] = _company()
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    min_hourly_rate: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PayBand(Base, RecordMixin, TenantMixin):
    __tablename__ = "pay_bands"
    __table_args__ = (
        CheckConstraint("min_annual >= 0 and max_annual >= min_annual", name="range"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency"),
        _unique_name("pay_bands", "name"),
    )

    company_id: Mapped[uuid.UUID] = _company()
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    min_annual: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    max_annual: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="GBP")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PaySchedule(Base, RecordMixin, TenantMixin):
    """How often people are paid, and on which day. A weekly, fortnightly or four-weekly schedule
    pays on a weekday (1 = Monday ... 7 = Sunday); a monthly one on a day of the month (1 to 28),
    the last day, or the last working day."""

    __tablename__ = "pay_schedules"
    __table_args__ = (
        CheckConstraint(
            "frequency in ('weekly', 'fortnightly', 'four_weekly', 'monthly')", name="frequency"
        ),
        CheckConstraint(
            "pay_day_kind in ('weekday', 'day_of_month', 'last_day', 'last_working_day')",
            name="pay_day_kind",
        ),
        CheckConstraint(
            "(pay_day_kind = 'weekday' and pay_day_value between 1 and 7)"
            " or (pay_day_kind = 'day_of_month' and pay_day_value between 1 and 28)"
            " or (pay_day_kind in ('last_day', 'last_working_day') and pay_day_value is null)",
            name="pay_day",
        ),
        _unique_name("pay_schedules", "name"),
    )

    company_id: Mapped[uuid.UUID] = _company()
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    frequency: Mapped[str] = mapped_column(String(12), nullable=False)
    pay_day_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    pay_day_value: Mapped[int | None] = mapped_column(SmallInteger)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
