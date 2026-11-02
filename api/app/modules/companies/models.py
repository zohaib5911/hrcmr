"""The company: one customer account (plan.md 6.1). Every tenant table points back at it."""

from __future__ import annotations

import uuid  # noqa: TC003  (SQLAlchemy resolves the Mapped[...] annotations at runtime)
from datetime import datetime  # noqa: TC003

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    SmallInteger,
    String,
    Text,
    Uuid,
    false,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin
from app.modules.companies.reference import (
    LEGAL_STRUCTURES,
    SECTORS,
    TRADING_PERIODS,
    check_sql,
)

COMPANY_STATUSES = ("active", "suspended", "pending_deletion", "deleted")
COMPANY_PLANS = ("free", "annual", "ten_year")
MFA_POLICIES = ("optional", "admins", "all")
BANK_HOLIDAY_REGIONS = ("england-and-wales", "scotland", "northern-ireland")
REGIONS = ("uk", "us", "au")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} in ({', '.join(repr(v) for v in values)})"


class Company(Base, RecordMixin):
    """Not a tenant table (it has no ``company_id``): it IS the tenant. Read it through a
    membership, never by listing."""

    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint(_in("status", COMPANY_STATUSES), name="status"),
        CheckConstraint(_in("plan", COMPANY_PLANS), name="plan"),
        CheckConstraint(_in("mfa_policy", MFA_POLICIES), name="mfa_policy"),
        CheckConstraint(
            _in("bank_holiday_region", BANK_HOLIDAY_REGIONS), name="bank_holiday_region"
        ),
        CheckConstraint(_in("region", REGIONS), name="region"),
        CheckConstraint(
            check_sql("type_of_organisation", LEGAL_STRUCTURES), name="type_of_organisation"
        ),
        CheckConstraint(check_sql("trading_period", TRADING_PERIODS), name="trading_period"),
        CheckConstraint(check_sql("sector", SECTORS), name="sector"),
        CheckConstraint("week_starts_on between 1 and 7", name="week_starts_on"),
        CheckConstraint(
            r"leave_year_start_month_day ~ '^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'",
            name="leave_year_start_month_day",
        ),
    )

    # Identity. The legal-structure, trading-period and sector lists are in ``reference.py``.
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    trading_name: Mapped[str | None] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    registered_number: Mapped[str | None] = mapped_column(String(20))
    type_of_organisation: Mapped[str | None] = mapped_column(String(60))
    trading_period: Mapped[str | None] = mapped_column(String(40))
    sector: Mapped[str | None] = mapped_column(String(10))
    size_band: Mapped[str | None] = mapped_column(String(20))

    # Contact and locale.
    contact_email: Mapped[str | None] = mapped_column(String(254))
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    website: Mapped[str | None] = mapped_column(String(300))
    # The logo is a row in ``files``; no foreign key, because ``files`` points back at companies.
    logo_file_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    country: Mapped[str] = mapped_column(String(2), nullable=False, server_default="GB")
    region: Mapped[str] = mapped_column(String(2), nullable=False, server_default="uk")
    bank_holiday_region: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="england-and-wales"
    )
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="Europe/London"
    )
    default_currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="GBP")
    week_starts_on: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")

    # Leave.
    leave_year_start_month_day: Mapped[str] = mapped_column(
        String(5), nullable=False, server_default="01-01"
    )
    allow_negative_leave_balance: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )

    # Security.
    mfa_policy: Mapped[str] = mapped_column(String(10), nullable=False, server_default="optional")
    # The company's own switch for the AI features (they also need the server's API key).
    ai_features_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=true()
    )

    # Sponsor history.
    changed_name_last_5_years: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    previous_company_name: Mapped[str | None] = mapped_column(String(200))
    penalty_illegal_working_last_3_years: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    penalty_illegal_working_status: Mapped[str | None] = mapped_column(Text)

    # Account.
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    plan: Mapped[str] = mapped_column(String(10), nullable=False, server_default="free")
    subscription_status: Mapped[str | None] = mapped_column(String(30))
    subscription_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    subscription_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cooling_off_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stripe_customer_id: Mapped[str | None] = mapped_column(String(80), unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(80), unique=True)
    setup_checklist_dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
