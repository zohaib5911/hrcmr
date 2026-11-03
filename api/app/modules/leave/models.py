"""Company leave types (plan 6.5); retained when archived for future ledger references."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003

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
    column,
    false,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin


class LeaveType(Base, RecordMixin, TenantMixin):
    __tablename__ = "leave_types"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_leave_types_company_id_id"),
        CheckConstraint("length(trim(name)) > 0", name="name"),
        CheckConstraint("days_per_year IS NULL OR days_per_year >= 0", name="days_per_year"),
        CheckConstraint("carry_over_limit_days >= 0", name="carry_over_limit_days"),
        CheckConstraint("accrual_method in ('front_loaded','monthly')", name="accrual_method"),
        CheckConstraint("colour in ('blue','green','orange','red','gray')", name="colour"),
        UniqueConstraint("company_id", "seed_key", name="uq_leave_types_company_id_seed_key"),
        Index(
            "uq_leave_types_company_id_name",
            "company_id",
            func.lower(column("name")),
            unique=True,
            postgresql_where=column("archived_at").is_(None),
        ),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    bank_holidays_included: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    seed_key: Mapped[str | None] = mapped_column(String(24))
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    counts_toward_statutory: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    days_per_year: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    carry_over_limit_days: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, server_default="0"
    )
    accrual_method: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default="front_loaded"
    )
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    colour: Mapped[str] = mapped_column(String(10), nullable=False, server_default="blue")
    rule_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    source_url: Mapped[str | None] = mapped_column(String(500))
    checked_on: Mapped[date | None] = mapped_column(Date)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LeaveLedger(Base, RecordMixin, TenantMixin):
    """Append-only signed movements. Corrections are new movements, never row edits."""

    __tablename__ = "leave_ledger"
    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "employee_id"],
            ["employees.company_id", "employees.id"],
            name="fk_leave_ledger_company_employee",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "leave_type_id"],
            ["leave_types.company_id", "leave_types.id"],
            name="fk_leave_ledger_company_type",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "entry_type in ('grant','accrual','carry_over','taken','adjustment',"
            "'deduct','set','year_end_expiry')",
            name="entry_type",
        ),
        CheckConstraint("length(trim(reason)) > 0", name="reason"),
        CheckConstraint(
            "(days <> 0 OR entry_type = 'set') AND days <> 'NaN'::numeric", name="days"
        ),
        CheckConstraint(
            "(entry_type not in ('grant','accrual','carry_over') or days > 0) and "
            "(entry_type not in ('taken','deduct','year_end_expiry') or days < 0)",
            name="sign",
        ),
        CheckConstraint("bucket is null or bucket in ('entitlement','calendar')", name="bucket"),
        UniqueConstraint(
            "company_id", "idempotency_key", name="uq_leave_ledger_company_id_idempotency_key"
        ),
        Index(
            "ix_leave_ledger_balance",
            "company_id",
            "employee_id",
            "leave_type_id",
            "leave_year_start",
        ),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    leave_type_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    leave_year_start: Mapped[date] = mapped_column(Date, nullable=False)
    entry_type: Mapped[str] = mapped_column(String(16), nullable=False)
    days: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    target_days: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    leave_request_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)  # FK added with requests T8.3
    bucket: Mapped[str | None] = mapped_column(String(16))
    idempotency_key: Mapped[uuid.UUID | None] = mapped_column(Uuid)
