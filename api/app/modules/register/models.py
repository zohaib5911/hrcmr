"""Global sponsor register snapshots; only the owner ingest connection writes them."""

from __future__ import annotations

import uuid
from datetime import date, datetime  # noqa: TC003
from typing import Any

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class Publication(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "register_publications"
    published_on: Mapped[date] = mapped_column(Date)
    source_url: Mapped[str] = mapped_column(String(2048))
    row_count: Mapped[int]
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(20), default="complete")


class Sponsor(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "register_sponsors"
    __table_args__ = (UniqueConstraint("normalised_name", "town", "county"),)
    stable_id: Mapped[str] = mapped_column(
        String(32), unique=True, default=lambda: uuid.uuid4().hex
    )
    organisation_name: Mapped[str] = mapped_column(String(1000))
    normalised_name: Mapped[str] = mapped_column(String(1000), index=True)
    town: Mapped[str] = mapped_column(String(500))
    county: Mapped[str] = mapped_column(String(500))
    region_itl1: Mapped[str | None] = mapped_column(String(100))
    lat: Mapped[float | None]
    lon: Mapped[float | None]
    place_precision: Mapped[str] = mapped_column(String(10), default="none")
    companies_house_number: Mapped[str | None] = mapped_column(String(20))
    sic_section: Mapped[str | None] = mapped_column(String(10))
    first_seen_on: Mapped[date] = mapped_column(Date)
    last_seen_on: Mapped[date] = mapped_column(Date)
    current: Mapped[bool]


class Entry(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "register_entries"
    __table_args__ = (UniqueConstraint("publication_id", "sponsor_id", "type_rating", "route"),)
    publication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("register_publications.id"), index=True
    )
    sponsor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("register_sponsors.id"), index=True)
    type_rating: Mapped[str] = mapped_column(String(300))
    route: Mapped[str] = mapped_column(String(300))


class Change(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "register_changes"
    publication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("register_publications.id"), index=True
    )
    sponsor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("register_sponsors.id"), index=True)
    change: Mapped[str] = mapped_column(String(30))
    detail: Mapped[dict[str, Any]] = mapped_column(JSON)


class PossibleMatch(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "register_possible_matches"
    __table_args__ = (UniqueConstraint("added_sponsor_id", "removed_sponsor_id"),)
    added_sponsor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("register_sponsors.id"))
    removed_sponsor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("register_sponsors.id"))
    similarity: Mapped[float]
    reason: Mapped[str] = mapped_column(String(300))


class ProblemReport(Base, UUIDPrimaryKeyMixin):
    """A visitor's "report a problem with an entry" (T20.4). Written by the public form only."""

    __tablename__ = "register_problem_reports"
    sponsor_stable_id: Mapped[str | None] = mapped_column(String(32), index=True)
    email: Mapped[str | None] = mapped_column(String(254))
    message: Mapped[str] = mapped_column(String(2000))
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
