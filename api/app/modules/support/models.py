"""A support-mode session (T17.3, plan 8.18): a platform admin looking at one company.

Started with a reason and a ticket reference; read-only until an owner-level admin enables writes
(with a second confirmation); over after 30 minutes or when ended. The company can read its own rows
(tenant isolation) and sees each start, write-enable and end in its audit trail.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin


class ImpersonationSession(Base, RecordMixin, TenantMixin):
    __tablename__ = "impersonation_sessions"
    __table_args__ = (
        CheckConstraint(
            "(write_enabled_at is null) = (write_enabled_by is null)", name="write_enabled_state"
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    started_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    ticket_ref: Mapped[str] = mapped_column(String(80), nullable=False)
    # The server-side session behind the support cookie (no key: sessions are pruned on their own).
    session_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    write_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    write_enabled_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
