"""Announcement banners (T17.5): a message for every company in one region, for a set period.

Global, with no company. ``ended_at`` is set when a platform admin ends one before its time; the
banner is then gone at once. Live means: started, not ended, and not yet past ``ends_at``.
"""

from __future__ import annotations

import uuid  # noqa: TC003  (SQLAlchemy resolves the Mapped[...] annotations at runtime)
from datetime import datetime  # noqa: TC003  (same)

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.modules.companies.models import REGIONS


class Announcement(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "announcements"
    __table_args__ = (
        CheckConstraint("region in (" + ", ".join(f"'{r}'" for r in REGIONS) + ")", name="region"),
        CheckConstraint("ends_at > starts_at", name="period"),
        Index("ix_announcements_region_period", "region", "ends_at"),
    )

    region: Mapped[str] = mapped_column(String(2), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(String(500), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
