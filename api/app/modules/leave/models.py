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
