"""Uploaded files (plan.md 6.1). The bytes live in object storage; this is what we know."""

from __future__ import annotations

import uuid  # noqa: TC003  (SQLAlchemy resolves the Mapped[...] annotations at runtime)
from datetime import datetime  # noqa: TC003

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin

SCAN_STATUSES = ("pending", "clean", "infected", "error")


class File(Base, RecordMixin, TenantMixin):
    __tablename__ = "files"
    __table_args__ = (
        CheckConstraint(
            "scan_status in ('pending', 'clean', 'infected', 'error')", name="scan_status"
        ),
        CheckConstraint("size >= 0", name="size"),
        Index("ix_files_owner", "owner_type", "owner_id"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Random, never derived from the file name or the person (plan 4.5).
    storage_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime: Mapped[str] = mapped_column(String(100), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # A file is not served until the scan says "clean".
    scan_status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="pending")
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # What it is attached to, such as ("employee", <id>); that table arrives with its module.
    owner_type: Mapped[str | None] = mapped_column(String(40))
    owner_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    category: Mapped[str | None] = mapped_column(String(40))
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
