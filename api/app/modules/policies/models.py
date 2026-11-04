"""Sent policy versions and completed receipts retain their original evidence."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    column,
    false,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin
from app.db.types import EncryptedString
from app.modules.policies.reference import POLICY_CATEGORIES


class PolicyDocument(Base, RecordMixin, TenantMixin):
    __tablename__ = "policy_documents"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_policy_documents_company_id_id"),
        UniqueConstraint(
            "company_id", "group_id", "version", name="uq_policy_documents_group_version"
        ),
        ForeignKeyConstraint(
            ["company_id", "file_id"],
            ["files.company_id", "files.id"],
            name="fk_policy_documents_file",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "group_id"],
            ["policy_documents.company_id", "policy_documents.id"],
            name="fk_policy_documents_group",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["company_id", "previous_version_id"],
            ["policy_documents.company_id", "policy_documents.id"],
            name="fk_policy_documents_previous",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "category in (" + ", ".join(repr(c) for c in POLICY_CATEGORIES) + ")", name="category"
        ),
        CheckConstraint("length(trim(title)) > 0", name="title"),
        CheckConstraint("confirmation_mode in ('accept','sign')", name="confirmation_mode"),
        CheckConstraint(
            "audience_type in ('everyone','departments','locations','named','visa_holders')",
            name="audience_type",
        ),
        CheckConstraint("status in ('draft','sent','archived')", name="status"),
        CheckConstraint(
            "cardinality(audience_ids) <= 500 and "
            "((audience_type in ('departments','locations','named')) = "
            "(cardinality(audience_ids) > 0))",
            name="audience_selection",
        ),
        CheckConstraint("accept_within_days between 1 and 365", name="accept_within_days"),
        CheckConstraint(
            "version > 0 and ((version=1) = (previous_version_id is null))", name="version"
        ),
        CheckConstraint(
            "status <> 'sent' or (file_id is not null and sent_at is not null "
            "and sent_by is not null)",
            name="sent_state",
        ),
        Index(
            "uq_policy_documents_live_draft",
            "company_id",
            "group_id",
            unique=True,
            postgresql_where=column("status") == "draft",
        ),
        Index(
            "uq_policy_documents_live_sent",
            "company_id",
            "group_id",
            unique=True,
            postgresql_where=column("status") == "sent",
        ),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    group_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    previous_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    file_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    confirmation_mode: Mapped[str] = mapped_column(
        String(6), nullable=False, server_default="accept"
    )
    audience_type: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default="everyone"
    )
    audience_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(Uuid), nullable=False, server_default="{}"
    )
    accept_within_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="14")
    auto_send_new_starters: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    status: Mapped[str] = mapped_column(String(8), nullable=False, server_default="draft")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT")
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PolicyAcceptance(Base, RecordMixin, TenantMixin):
    __tablename__ = "policy_acceptances"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "policy_document_id", "employee_id", name="uq_policy_acceptances_employee"
        ),
        ForeignKeyConstraint(
            ["company_id", "policy_document_id"],
            ["policy_documents.company_id", "policy_documents.id"],
            name="fk_policy_acceptances_document",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "employee_id"],
            ["employees.company_id", "employees.id"],
            name="fk_policy_acceptances_employee",
            ondelete="RESTRICT",
        ),
        CheckConstraint("status in ('pending','accepted','signed','overdue')", name="status"),
        CheckConstraint(
            "(status in ('accepted','signed')) = (accepted_at is not null)", name="accepted_state"
        ),
        CheckConstraint(
            "(status in ('accepted','signed')) = (accepted_by is not null)", name="actor_state"
        ),
        CheckConstraint(
            "(status = 'signed') = (typed_signature is not null)", name="signature_state"
        ),
        Index("ix_policy_acceptances_due", "company_id", "status", "due_on"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    policy_document_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    due_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(8), nullable=False, server_default="pending")
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT")
    )
    typed_signature: Mapped[str | None] = mapped_column(
        EncryptedString("policy_acceptances.typed_signature")
    )
    ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    last_reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
