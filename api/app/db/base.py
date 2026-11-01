"""Declarative base and the column mixins every table uses (plan.md section 6 conventions).

    class Employee(Base, RecordMixin, TenantMixin):
        __tablename__ = "employees"
        ...

``RecordMixin`` gives id (UUID v7), created_at, updated_at, created_by, updated_by.
``TenantMixin`` adds the indexed ``company_id`` that Row-Level Security and the tenant session
filter on.
Every migration that creates such a table must also call ``enable_tenant_rls`` and
``add_updated_at_trigger`` (app/db/rls.py); a test fails if one is forgotten.
"""

from __future__ import annotations

import uuid  # noqa: TC003  (SQLAlchemy resolves the Mapped[...] annotations at runtime)
from datetime import datetime  # noqa: TC003
from typing import Any, ClassVar

from sqlalchemy import DateTime, FetchedValue, MetaData, Uuid, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db.ids import uuid7

# Stable, predictable constraint names make migrations reviewable and downgrades reliable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid7,
        server_default=text("uuid_generate_v7()"),
    )


class TimestampMixin:
    # Async sessions cannot lazily reload an expired attribute, so fetch the trigger-maintained
    # `updated_at` in the same round trip as the INSERT / UPDATE (RETURNING).
    __mapper_args__: ClassVar[dict[str, Any]] = {"eager_defaults": True}

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Kept current by the `trg_set_updated_at` trigger, so raw SQL updates are covered too;
    # FetchedValue makes the ORM re-read it after an UPDATE.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        server_onupdate=FetchedValue(),
        nullable=False,
    )


class AuditColumnsMixin:
    """Who created / last changed the row. Filled from the session's user. No foreign key: the
    people table is global and rows must survive a user being purged."""

    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class RecordMixin(UUIDPrimaryKeyMixin, TimestampMixin, AuditColumnsMixin):
    """The five columns the plan puts on every table."""


class TenantMixin:
    """Marks a table as belonging to one company. Row-Level Security filters on this column."""

    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
