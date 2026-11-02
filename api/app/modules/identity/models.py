"""People who can sign in, and how they belong to companies (plan.md 6.1).

Two kinds of table live here:

* ``users``, ``platform_admins``, ``email_tokens``, ``terms_*`` and ``sessions`` are about a person
  or a token, not a company. ``sessions`` and ``invitations`` are read BEFORE a company is known (a
  cookie or an emailed link is all there is), so they are in ``PRE_TENANT_TABLES`` and are reached
  only through ``GlobalSession``, by the authentication service.
* ``memberships`` is the link between a person and a company. It is a tenant table, and also
  readable by the person it is about, so sign-in can list their companies.
"""

from __future__ import annotations

import uuid  # noqa: TC003  (SQLAlchemy resolves the Mapped[...] annotations at runtime)
from datetime import datetime  # noqa: TC003

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    column,
    false,
    func,
    true,
)
from sqlalchemy.dialects.postgresql import CITEXT, INET
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import EncryptedString

ROLES = (
    "company_admin",
    "hr_admin",
    "people_manager",
    "recruiter",
    "employee",
    "read_only_auditor",
)
MEMBERSHIP_STATUSES = ("active", "suspended")
PLATFORM_LEVELS = ("support", "owner")
EMAIL_TOKEN_PURPOSES = ("verify", "reset", "deletion_code", "login_alert")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} in ({', '.join(repr(v) for v in values)})"


class User(Base, RecordMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())

    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    mfa_secret: Mapped[str | None] = mapped_column(EncryptedString("users.mfa_secret"))
    recovery_codes_hash: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )

    requires_password_change: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    theme_pref: Mapped[str] = mapped_column(String(10), nullable=False, server_default="system")

    __table_args__ = (
        CheckConstraint(_in("theme_pref", ("system", "light", "dark")), name="theme_pref"),
        CheckConstraint("failed_login_count >= 0", name="failed_login_count"),
    )


class Membership(Base, RecordMixin, TenantMixin):
    __tablename__ = "memberships"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="active")
    # The HR record this person is. The employees table arrives in Phase 4, with the foreign key.
    employee_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)

    __table_args__ = (
        UniqueConstraint("user_id", "company_id", name="uq_memberships_user_id_company_id"),
        Index(
            "uq_memberships_company_id_employee_id",
            "company_id",
            "employee_id",
            unique=True,
            postgresql_where=column("employee_id").is_not(None),
        ),
        CheckConstraint(_in("role", ROLES), name="role"),
        CheckConstraint(_in("status", MEMBERSHIP_STATUSES), name="status"),
    )


class PlatformAdmin(Base, RecordMixin):
    """Our own staff. MFA is always required for them, which is why there is no switch for it."""

    __tablename__ = "platform_admins"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    level: Mapped[str] = mapped_column(String(10), nullable=False)

    __table_args__ = (CheckConstraint(_in("level", PLATFORM_LEVELS), name="level"),)


class Session(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A signed-in browser. Only a hash of the token is stored, so a leak is not a login."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The active company; empty for a platform admin or before one is chosen.
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(String(400))
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mfa_passed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    step_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Invitation(Base, RecordMixin):
    __tablename__ = "invitations"

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (CheckConstraint(_in("role", ROLES), name="role"),)


class EmailToken(Base, RecordMixin):
    """A one-time code sent by email: verify an address, reset a password, confirm a deletion."""

    __tablename__ = "email_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint(_in("purpose", EMAIL_TOKEN_PURPOSES), name="purpose"),)


class TermsVersion(Base, RecordMixin):
    __tablename__ = "terms_versions"

    version: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    url: Mapped[str] = mapped_column(String(300), nullable=False)


class TermsAcceptance(Base, RecordMixin):
    __tablename__ = "terms_acceptances"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(
        String(40), ForeignKey("terms_versions.version", ondelete="RESTRICT"), nullable=False
    )
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ip: Mapped[str | None] = mapped_column(INET)

    __table_args__ = (
        UniqueConstraint("user_id", "version", name="uq_terms_acceptances_user_id_version"),
    )
