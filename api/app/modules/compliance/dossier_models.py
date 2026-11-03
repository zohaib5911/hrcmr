"""Global official guidance links, edited only by platform content administrators."""

from __future__ import annotations

from datetime import date  # noqa: TC003

from sqlalchemy import Boolean, CheckConstraint, Date, Integer, String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin


class DossierLink(Base, RecordMixin):
    __tablename__ = "dossier_links"
    __table_args__ = (
        CheckConstraint("section in ('licence', 'rtw', 'sms')", name="section"),
        CheckConstraint("position >= 0", name="position"),
        CheckConstraint("url ~ '^https://www[.]gov[.]uk/[^[:space:]]+$'", name="official_url"),
    )

    section: Mapped[str] = mapped_column(String(10), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    checked_on: Mapped[date] = mapped_column(Date, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
