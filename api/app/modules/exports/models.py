"""A company's data export (T16.4, plan 8.16): the request, and the zip once it is built.

The zip is a private file (``files`` row). The download lasts 7 days from when it was made
(``expires_at``); a download always needs the requester's signed-in session.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin


class DataExport(Base, RecordMixin, TenantMixin):
    __tablename__ = "data_exports"
    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "file_id"],
            ["files.company_id", "files.id"],
            name="fk_data_exports_file",
            ondelete="RESTRICT",
        ),
        CheckConstraint("status in ('queued','ready','failed')", name="status"),
        CheckConstraint("(status = 'ready') = (file_id is not null)", name="file_state"),
        CheckConstraint("(status = 'ready') = (expires_at is not null)", name="expiry_state"),
        CheckConstraint("(status = 'queued') = (finished_at is null)", name="finished_state"),
        CheckConstraint("(status = 'failed') = (error_code is not null)", name="error_state"),
        Index("ix_data_exports_requester", "company_id", "requested_by", "created_at"),
        # One queued export per company (ISS-25): a concurrent second request loses here.
        Index(
            "uq_data_exports_one_queued",
            "company_id",
            unique=True,
            postgresql_where=text("status = 'queued'"),
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="queued")
    file_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(40))
