"""Right to Work checks (plan 6.4): encrypted codes and versioned evidence records."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    column,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin
from app.db.types import EncryptedString

FOLLOW_UP = "CASE WHEN permission_expires THEN permission_expires_on ELSE NULL END"
CONDITIONS = {
    "subject_type": ("subject_type in ('employee', 'candidate')"),
    "check_type": (
        "check_type in ('online_share_code', 'idsp_digital', 'manual_list_a', 'manual_list_b')"
    ),
    "outcome": ("outcome in ('pending', 'verified', 'failed')"),
    "employee_checker": (
        "subject_type <> 'employee' or (check_date is not null and checked_by_user_id is not null)"
    ),
    "permission_expiry": (
        "(permission_expires and permission_expires_on is not null) or (not "
        "permission_expires and permission_expires_on is null)"
    ),
    "online_code": (
        "(check_type = 'online_share_code' and share_code is not null) or "
        "(check_type <> 'online_share_code' and share_code is null)"
    ),
    "idsp": (
        "(check_type = 'idsp_digital' and idsp_provider is not null and "
        "idsp_document is not null and idsp_document in ('british_passport', "
        "'irish_passport', 'irish_passport_card')) or (check_type <> 'idsp_digital' "
        "and idsp_provider is null and idsp_document is null)"
    ),
    "list_b": (
        "(check_type = 'manual_list_b' and list_b_group is not null and list_b_group"
        " in ('group1', 'group2') and permission_expires) or (check_type <> "
        "'manual_list_b' and list_b_group is null)"
    ),
    "indefinite": ("check_type not in ('idsp_digital', 'manual_list_a') or not permission_expires"),
    "correction": (
        "(corrected_from_id is null and correction_reason is null) or "
        "(corrected_from_id is not null and correction_reason is not null and "
        "length(trim(correction_reason)) > 0)"
    ),
    "superseded": (
        "(superseded_at is null and superseded_by is null) or superseded_at is not null"
    ),
}


class RTWCheck(Base, RecordMixin, TenantMixin):
    __tablename__ = "rtw_checks"
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    subject_type: Mapped[str] = mapped_column(String(9), nullable=False)
    # Polymorphic subject: employee existence/scope is checked before every API operation;
    # Phase 11 adds candidate validation when the candidate module exists.
    subject_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    check_type: Mapped[str] = mapped_column(String(24), nullable=False)
    share_code: Mapped[str | None] = mapped_column(EncryptedString("rtw_checks.share_code"))
    idsp_provider: Mapped[str | None] = mapped_column(String(160))
    idsp_document: Mapped[str | None] = mapped_column(String(24))
    list_b_group: Mapped[str | None] = mapped_column(String(6))
    permission_expires: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    permission_expires_on: Mapped[date | None] = mapped_column(Date)
    follow_up_due_on: Mapped[date | None] = mapped_column(Date, Computed(FOLLOW_UP, persisted=True))
    check_date: Mapped[date | None] = mapped_column(Date)
    checked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT")
    )
    outcome: Mapped[str] = mapped_column(String(8), nullable=False)
    evidence_file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("files.id", ondelete="RESTRICT")
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("rtw_checks.id", ondelete="RESTRICT", deferrable=True, initially="DEFERRED"),
    )
    corrected_from_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("rtw_checks.id", ondelete="RESTRICT"), unique=True
    )
    correction_reason: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        *(CheckConstraint(sql, name=name) for name, sql in CONDITIONS.items()),
        Index("ix_rtw_checks_subject", "company_id", "subject_type", "subject_id"),
        Index(
            "uq_rtw_checks_current",
            "company_id",
            "subject_type",
            "subject_id",
            unique=True,
            postgresql_where=column("superseded_at").is_(None),
        ),
    )
