"""Courses (global, written by us, edited only by super-admin) and each person's assignment to one.

Plan 6.9: a course is shared by every company, so ``courses`` has no company column. Each assignment
belongs to one company and one employee and is protected by Row-Level Security.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date, datetime  # noqa: TC003
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    false,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin, TenantMixin


class Course(Base, RecordMixin):
    __tablename__ = "courses"
    __table_args__ = (
        CheckConstraint("audience in ('all_staff', 'managers')", name="audience"),
        CheckConstraint("duration_minutes between 5 and 120", name="duration_minutes"),
        CheckConstraint("pass_mark between 1 and 100", name="pass_mark"),
        CheckConstraint("source_url like 'https://%'", name="source_url"),
        CheckConstraint("version >= 1", name="version"),
    )

    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str] = mapped_column(String(400), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    audience: Mapped[str] = mapped_column(String(12), nullable=False)
    sections: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    quiz: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    pass_mark: Mapped[int] = mapped_column(Integer, nullable=False)
    source_title: Mapped[str] = mapped_column(String(200), nullable=False)
    source_publisher: Mapped[str] = mapped_column(String(120), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_updated_on: Mapped[date] = mapped_column(Date, nullable=False)
    content_reviewed_on: Mapped[date] = mapped_column(Date, nullable=False)
    licence_note: Mapped[str | None] = mapped_column(String(400))
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class CourseAssignment(Base, RecordMixin, TenantMixin):
    __tablename__ = "course_assignments"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "course_id", "employee_id", name="uq_course_assignments_one_per_person"
        ),
        CheckConstraint(
            "status in ('not_started', 'in_progress', 'completed', 'overdue')", name="status"
        ),
        CheckConstraint("quiz_score is null or quiz_score between 0 and 100", name="quiz_score"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    due_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="not_started")
    progress: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    quiz_score: Mapped[int | None] = mapped_column(Integer)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )


class Certificate(Base, RecordMixin):
    """Proof that a person completed a course. The public check finds it by its reference.

    The holder and course names are copied when it is issued, so later edits do not change it."""

    __tablename__ = "certificates"
    __table_args__ = (CheckConstraint("length(reference) >= 10", name="reference_length"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("course_assignments.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    reference: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    holder_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    course_title_snapshot: Mapped[str] = mapped_column(String(160), nullable=False)
    completed_on: Mapped[date] = mapped_column(Date, nullable=False)
    issued_on: Mapped[date] = mapped_column(Date, nullable=False)
