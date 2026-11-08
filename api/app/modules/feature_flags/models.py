"""Feature flags (T17.5): one row per named feature, switched on or off by a platform admin.

Global, with no company: a flag is the same for everyone. ``key`` is the flag's name and is its
primary key. ``updated_by`` is the platform admin who last changed it.
"""

from __future__ import annotations

import uuid  # noqa: TC003  (SQLAlchemy resolves the Mapped[...] annotations at runtime)
from datetime import datetime  # noqa: TC003  (same)

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Uuid, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FeatureFlag(Base):
    __tablename__ = "feature_flags"
    __table_args__ = (CheckConstraint("key ~ '^[a-z][a-z0-9_]{2,59}$'", name="key_format"),)

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    description: Mapped[str] = mapped_column(String(300), nullable=False, server_default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
