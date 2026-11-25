"""A company's request to delete its account (T16.5, plan 8.16).

The admin asks, a 6-digit code is e-mailed, and entering it schedules the deletion 7 days on; it can
be withdrawn until then. The row is kept after the purge as the company's deletion record (the
person who asked may be gone, so ``requested_by`` empties).
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Uuid,
    and_,
    column,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin


class DeletionRequest(Base, RecordMixin, TenantMixin):
    __tablename__ = "deletion_requests"
    __table_args__ = (
        CheckConstraint("(confirmed_at is null) = (scheduled_for is null)", name="scheduled_state"),
        CheckConstraint(
            "completed_at is null or (confirmed_at is not null and withdrawn_at is null)",
            name="completed_state",
        ),
        CheckConstraint("code_attempts between 0 and 10", name="code_attempts"),
        Index(
            "uq_deletion_requests_open",
            "company_id",
            unique=True,
            postgresql_where=and_(
                column("withdrawn_at").is_(None), column("completed_at").is_(None)
            ),
        ),
        Index(
            "ix_deletion_requests_due",
            "scheduled_for",
            postgresql_where=and_(
                column("confirmed_at").is_not(None),
                column("withdrawn_at").is_(None),
                column("completed_at").is_(None),
            ),
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    code_hash: Mapped[str | None] = mapped_column(String(64))
    code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    code_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    export_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    export_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # ISS-30: after a failed purge the request waits until this time, so a batch of persistent
    # failures cannot hold back companies behind it. Null = due now.
    failures: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
