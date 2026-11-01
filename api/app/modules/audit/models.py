"""The audit trail (plan.md 6.1 and 4.5): who did what, to what, when. Append-only.

Nothing may change or remove a row: the table has no UPDATE or DELETE grant for the application
role, and a trigger refuses both (and TRUNCATE) for every role, the owner included.
"""

from __future__ import annotations

import uuid  # noqa: TC003  (SQLAlchemy resolves the Mapped[...] annotations at runtime)
from datetime import datetime  # noqa: TC003
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin

ACTOR_TYPES = ("user", "platform_admin", "system")


class AuditEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint("actor_type in ('user', 'platform_admin', 'system')", name="actor_type"),
        Index("ix_audit_events_company_id_created_at", "company_id", "created_at"),
        Index("ix_audit_events_entity", "entity_type", "entity_id"),
    )

    # Empty for platform-level events. Row-Level Security therefore hides those from every company.
    company_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)

    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(60))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    summary: Mapped[str | None] = mapped_column(Text)
    # Sensitive fields are masked before they are written (T2.6).
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)

    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(String(400))
    request_id: Mapped[str | None] = mapped_column(String(64))
    impersonation_session_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
