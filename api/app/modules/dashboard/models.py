"""The set-up checklist's dismissal, one row per person and company (plan 8.2)."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin


class OnboardingDismissal(Base, RecordMixin, TenantMixin):
    __tablename__ = "onboarding_dismissals"
    __table_args__ = (
        UniqueConstraint("company_id", "user_id", name="uq_onboarding_dismissals_company_user"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    dismissed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
