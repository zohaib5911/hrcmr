"""The company: one customer account (plan.md 6.1). Every tenant table points back at it."""

from __future__ import annotations

import uuid  # noqa: TC003  (SQLAlchemy resolves the Mapped[...] annotations at runtime)
from datetime import date, datetime, time  # noqa: TC003

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
    and_,
    column,
    false,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin
from app.modules.companies.reference import (
    COMPLIANCE_DOCUMENT_TYPES,
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
    # The working pattern's one company-wide switch: bank holidays are days nobody works.
    bank_holidays_non_working: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=true()
    )
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


class Location(Base, RecordMixin, TenantMixin):
    """A place the company works from. At most one is the default (its main address)."""

    __tablename__ = "locations"
    __table_args__ = (
        # One default per company among the locations still in use.
        Index(
            "uq_locations_company_id_default",
            "company_id",
            unique=True,
            postgresql_where=and_(column("is_default").is_(True), column("archived_at").is_(None)),
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    postcode: Mapped[str] = mapped_column(String(10), nullable=False)
    address_line1: Mapped[str] = mapped_column(String(120), nullable=False)
    address_line2: Mapped[str | None] = mapped_column(String(120))
    address_line3: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    county: Mapped[str | None] = mapped_column(String(80))
    country: Mapped[str] = mapped_column(
        String(60), nullable=False, server_default="United Kingdom"
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Department(Base, RecordMixin, TenantMixin):
    __tablename__ = "departments"
    __table_args__ = (
        Index(
            "uq_departments_company_id_name",
            "company_id",
            func.lower(column("name")),
            unique=True,
            postgresql_where=column("archived_at").is_(None),
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Designation(Base, RecordMixin, TenantMixin):
    """A job title in a department, optionally tied to a SOC (occupation) code."""

    __tablename__ = "designations"
    __table_args__ = (
        CheckConstraint(r"soc_code ~ '^[0-9]{4}$'", name="soc_code"),
        Index(
            "uq_designations_department_id_title",
            "department_id",
            func.lower(column("title")),
            unique=True,
            postgresql_where=column("archived_at").is_(None),
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    soc_code: Mapped[str | None] = mapped_column(String(4))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


KEY_PERSON_ROLES = ("authorising_officer", "key_contact", "level1_user", "level2_user")


class KeyPerson(Base, RecordMixin, TenantMixin):
    """A person the Home Office knows the company by (plan.md 8.15). Level 2 users can be many; the
    other three roles are held by one person each."""

    __tablename__ = "key_persons"
    __table_args__ = (
        CheckConstraint(_in("role", KEY_PERSON_ROLES), name="role"),
        Index(
            "uq_key_persons_company_id_role",
            "company_id",
            "role",
            unique=True,
            postgresql_where=and_(column("role") != "level2_user", column("archived_at").is_(None)),
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    designation: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(254))
    # The scanned identity document, in file storage (never the bytes in the database).
    proof_of_id_file_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    # This person is the Authorising Officer too: their details follow the officer's.
    same_as_authorising_officer: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    # The form asks whether the person is a British citizen or settled in the UK (yes or no).
    is_settled_or_british: Mapped[bool | None] = mapped_column(Boolean)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ComplianceDocument(Base, RecordMixin, TenantMixin):
    """One of the company's licence documents. One is current per type; a new upload replaces it
    and the old record is archived (the file itself is kept)."""

    __tablename__ = "company_compliance_documents"
    __table_args__ = (
        CheckConstraint(check_sql("doc_type", COMPLIANCE_DOCUMENT_TYPES), name="doc_type"),
        Index(
            "uq_company_compliance_documents_company_id_doc_type",
            "company_id",
            "doc_type",
            unique=True,
            postgresql_where=column("archived_at").is_(None),
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    doc_type: Mapped[str] = mapped_column(String(40), nullable=False)
    file_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("files.id", ondelete="RESTRICT"), nullable=False
    )
    expires_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TradingHoursDay(Base, RecordMixin, TenantMixin):
    """When the business is open on one weekday (1 = Monday ... 7 = Sunday). A day with no row has
    not been set yet and is shown as closed."""

    __tablename__ = "trading_hours_days"
    __table_args__ = (
        CheckConstraint("weekday between 1 and 7", name="weekday"),
        CheckConstraint(
            "(is_open and opens_at is not null and closes_at is not null and opens_at < closes_at)"
            " or (not is_open and opens_at is null and closes_at is null)",
            name="times",
        ),
        UniqueConstraint("company_id", "weekday", name="uq_trading_hours_days_company_id_weekday"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    opens_at: Mapped[time | None] = mapped_column(Time)
    closes_at: Mapped[time | None] = mapped_column(Time)
