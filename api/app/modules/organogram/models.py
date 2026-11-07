"""Org chart hierarchy levels (plan 6.2): a label with an order. It does not change access."""

from __future__ import annotations

import uuid  # noqa: TC003

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Uuid, column, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin


class OrganogramLevel(Base, RecordMixin, TenantMixin):
    __tablename__ = "organogram_levels"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name"),
        CheckConstraint("rank >= 1", name="rank"),
        Index(
            "uq_organogram_levels_company_id_name",
            "company_id",
            func.lower(column("name")),
            unique=True,
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
