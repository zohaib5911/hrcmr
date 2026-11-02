"""Employees (plan.md 6.3): the HR record and everything that hangs off it. Every table is the
company's own (row-level security). Sub-records belong to one employee and go with it if a record
made by mistake is permanently deleted; ordinary leavers are kept (status ``leaver``/``archived``).

Role, reporting lines and working terms live in ``employee_assignments`` and pay in
``employee_compensation``: both are effective-dated and never overwritten, the current row being
the one with no end date (assignments) or the latest start not in the future (compensation)."""

from __future__ import annotations

import uuid  # noqa: TC003  (SQLAlchemy resolves the Mapped[...] annotations at runtime)
from datetime import date  # noqa: TC003
from decimal import Decimal  # noqa: TC003
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Uuid,
    column,
    false,
    func,
    literal_column,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin
from app.db.types import EncryptedString

STATUSES = ("active", "on_leave", "leaver", "archived")
RELATIONSHIPS = (
    "spouse",
    "civil_partner",
    "partner",
    "parent",
    "child",
    "sibling",
    "guardian",
    "other_relative",
    "friend",
    "other",
)
EMPLOYMENT_TYPES = (
    "full_time",
    "part_time",
    "fixed_term",
    "zero_hours",
    "casual",
    "apprentice",
    "agency",
)
FREQUENCIES = ("annual", "monthly", "hourly")
DOCUMENT_CATEGORIES = (
    "employment_contract",
    "letter",
    "hr_record",
    "id_document",
    "rtw_evidence",
    "certificate",
    "payslip",
    "other",
)


def _in(name: str, values: tuple[str, ...]) -> str:
    return f"{name} in ({', '.join(repr(v) for v in values)})"


def _company() -> Mapped[uuid.UUID]:
    return mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )


def _employee() -> Mapped[uuid.UUID]:
    return mapped_column(
        Uuid, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )


def _optional_fk(target: str) -> Mapped[uuid.UUID | None]:
    return mapped_column(Uuid, ForeignKey(target, ondelete="SET NULL"))


class Employee(Base, RecordMixin, TenantMixin):
    __tablename__ = "employees"

    company_id: Mapped[uuid.UUID] = _company()
    employee_number: Mapped[str] = mapped_column(String(50), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))
    alt_phone: Mapped[str | None] = mapped_column(String(40))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(30))
    marital_status: Mapped[str | None] = mapped_column(String(30))
    nationality: Mapped[str | None] = mapped_column(String(80))
    photo_file_id: Mapped[uuid.UUID | None] = _optional_fk("files.id")

    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="active")
    leave_date: Mapped[date | None] = mapped_column(Date)
    opted_out_48h_week: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )

    # Sensitive: encrypted at rest. The NI number also has a blind index (a keyed hash) so a
    # duplicate can be found without decrypting anyone's record.
    ni_number: Mapped[str | None] = mapped_column(EncryptedString("employees.ni_number"))
    ni_number_index: Mapped[str | None] = mapped_column(String(64))
    passport_number: Mapped[str | None] = mapped_column(
        EncryptedString("employees.passport_number")
    )
    passport_country: Mapped[str | None] = mapped_column(String(80))
    passport_expiry: Mapped[date | None] = mapped_column(Date)

    __table_args__ = (
        Index(
            "uq_employees_company_id_employee_number",
            "company_id",
            func.lower(
                func.regexp_replace(
                    column("employee_number"),
                    literal_column("'\\s'"),
                    literal_column("''"),
                    literal_column("'g'"),
                )
            ),
            unique=True,
        ),
        Index("ix_employees_company_id_status", "company_id", "status"),
        Index(
            "ix_employees_company_id_ni_number_index",
            "company_id",
            "ni_number_index",
            postgresql_where=column("ni_number_index").is_not(None),
        ),
        CheckConstraint(_in("status", STATUSES), name="status"),
    )


class EmployeeAddress(Base, RecordMixin, TenantMixin):
    __tablename__ = "employee_addresses"

    company_id: Mapped[uuid.UUID] = _company()
    employee_id: Mapped[uuid.UUID] = _employee()
    postcode: Mapped[str | None] = mapped_column(String(12))
    line1: Mapped[str] = mapped_column(String(120), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(120))
    line3: Mapped[str | None] = mapped_column(String(120))
    city_county: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(80))
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())


class EmergencyContact(Base, RecordMixin, TenantMixin):
    __tablename__ = "emergency_contacts"

    company_id: Mapped[uuid.UUID] = _company()
    employee_id: Mapped[uuid.UUID] = _employee()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    relationship: Mapped[str] = mapped_column(String(20), nullable=False)
    phone: Mapped[str] = mapped_column(String(40), nullable=False)
    email: Mapped[str | None] = mapped_column(String(254))
    address: Mapped[str | None] = mapped_column(Text)
    details: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (CheckConstraint(_in("relationship", RELATIONSHIPS), name="relationship"),)


class EmployeeBankDetail(Base, RecordMixin, TenantMixin):
    """One current account per employee; replaced accounts are kept as history."""

    __tablename__ = "employee_bank_details"

    company_id: Mapped[uuid.UUID] = _company()
    employee_id: Mapped[uuid.UUID] = _employee()
    account_holder: Mapped[str] = mapped_column(String(120), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(120), nullable=False)
    sort_code: Mapped[str] = mapped_column(
        EncryptedString("employee_bank_details.sort_code"), nullable=False
    )
    account_number: Mapped[str] = mapped_column(
        EncryptedString("employee_bank_details.account_number"), nullable=False
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())

    __table_args__ = (
        Index(
            "uq_employee_bank_details_employee_id_current",
            "employee_id",
            unique=True,
            postgresql_where=column("is_current"),
        ),
    )


class EmployeeAssignment(Base, RecordMixin, TenantMixin):
    """Role, reporting lines and working terms from a date. A change ends the current row and adds
    a new one; nothing is overwritten."""

    __tablename__ = "employee_assignments"

    company_id: Mapped[uuid.UUID] = _company()
    employee_id: Mapped[uuid.UUID] = _employee()
    department_id: Mapped[uuid.UUID | None] = _optional_fk("departments.id")
    designation_id: Mapped[uuid.UUID | None] = _optional_fk("designations.id")
    location_id: Mapped[uuid.UUID | None] = _optional_fk("locations.id")
    reporting_authority_employee_id: Mapped[uuid.UUID | None] = _optional_fk("employees.id")
    leave_sanctioning_employee_id: Mapped[uuid.UUID | None] = _optional_fk("employees.id")
    organogram_level_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)  # table comes in T12.1
    employment_type: Mapped[str] = mapped_column(String(12), nullable=False)
    custom_working_days: Mapped[Any | None] = mapped_column(JSONB)
    hours_per_day: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    ended_at: Mapped[date | None] = mapped_column(Date)

    __table_args__ = (
        Index(
            "uq_employee_assignments_employee_id_current",
            "employee_id",
            unique=True,
            postgresql_where=column("ended_at").is_(None),
        ),
        Index(
            "ix_employee_assignments_reporting",
            "reporting_authority_employee_id",
            postgresql_where=column("ended_at").is_(None),
        ),
        Index(
            "ix_employee_assignments_leave",
            "leave_sanctioning_employee_id",
            postgresql_where=column("ended_at").is_(None),
        ),
        CheckConstraint(_in("employment_type", EMPLOYMENT_TYPES), name="employment_type"),
    )


class EmployeeResponsibility(Base, RecordMixin, TenantMixin):
    __tablename__ = "employee_responsibilities"

    company_id: Mapped[uuid.UUID] = _company()
    employee_id: Mapped[uuid.UUID] = _employee()
    text: Mapped[str] = mapped_column(Text, nullable=False)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class EmployeeCompensation(Base, RecordMixin, TenantMixin):
    """Pay history. The current row is the latest one whose start date is not in the future."""

    __tablename__ = "employee_compensation"

    company_id: Mapped[uuid.UUID] = _company()
    employee_id: Mapped[uuid.UUID] = _employee()
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    frequency: Mapped[str] = mapped_column(String(10), nullable=False)
    contracted_hours_per_week: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    tax_code_id: Mapped[uuid.UUID | None] = _optional_fk("tax_codes.id")
    payment_type_id: Mapped[uuid.UUID | None] = _optional_fk("payment_types.id")
    pay_band_id: Mapped[uuid.UUID | None] = _optional_fk("pay_bands.id")
    pay_schedule_id: Mapped[uuid.UUID | None] = _optional_fk("pay_schedules.id")
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        CheckConstraint(_in("frequency", FREQUENCIES), name="frequency"),
        CheckConstraint("amount >= 0", name="amount"),
    )


class EmployeePreviousEmployment(Base, RecordMixin, TenantMixin):
    __tablename__ = "employee_previous_employment"

    company_id: Mapped[uuid.UUID] = _company()
    employee_id: Mapped[uuid.UUID] = _employee()
    job_title: Mapped[str | None] = mapped_column(String(120))
    started_on: Mapped[date | None] = mapped_column(Date)
    left_on: Mapped[date | None] = mapped_column(Date)
    total_experience_years: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    description: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("uq_employee_previous_employment_employee_id", "employee_id", unique=True),
    )


class EmployeeEducation(Base, RecordMixin, TenantMixin):
    __tablename__ = "employee_education"

    company_id: Mapped[uuid.UUID] = _company()
    employee_id: Mapped[uuid.UUID] = _employee()
    qualification: Mapped[str] = mapped_column(String(120), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(120))
    institution: Mapped[str | None] = mapped_column(String(120))
    awarding_body: Mapped[str | None] = mapped_column(String(120))
    year: Mapped[int | None] = mapped_column(SmallInteger)
    percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    grade: Mapped[str | None] = mapped_column(String(40))


class EmployeeTrainingRecord(Base, RecordMixin, TenantMixin):
    __tablename__ = "employee_training_records"

    company_id: Mapped[uuid.UUID] = _company()
    employee_id: Mapped[uuid.UUID] = _employee()
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    started_on: Mapped[date | None] = mapped_column(Date)
    ended_on: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)


class EmployeeMembership(Base, RecordMixin, TenantMixin):
    """A professional licence or membership (not a sign-in membership)."""

    __tablename__ = "employee_memberships"

    company_id: Mapped[uuid.UUID] = _company()
    employee_id: Mapped[uuid.UUID] = _employee()
    licence_title: Mapped[str] = mapped_column(String(160), nullable=False)
    licence_number: Mapped[str | None] = mapped_column(String(80))
    started_on: Mapped[date | None] = mapped_column(Date)
    ended_on: Mapped[date | None] = mapped_column(Date)


class EmployeeDocument(Base, RecordMixin, TenantMixin):
    __tablename__ = "employee_documents"

    company_id: Mapped[uuid.UUID] = _company()
    employee_id: Mapped[uuid.UUID] = _employee()
    file_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("files.id", ondelete="RESTRICT"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (CheckConstraint(_in("category", DOCUMENT_CATEGORIES), name="category"),)


def current_assignment() -> Any:
    """Assignments are active on [effective_from, ended_at), including scheduled changes."""
    return (EmployeeAssignment.effective_from <= func.current_date()) & (
        EmployeeAssignment.ended_at.is_(None) | (EmployeeAssignment.ended_at > func.current_date())
    )
