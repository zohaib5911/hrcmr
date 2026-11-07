"""Immigration rules data for the Sponsorship Job Checker (plan 6.10, T15.2).

Global, like the SOC tables: no company column, every tenant may read, only the owner role writes.
Each import makes one ``rules_versions`` row (a ``draft``); every rate, list entry and salary rule
hangs off it, so a saved check keeps the exact figures it was made with. Nothing here is typed by
hand: the importer parses the GOV.UK pages saved in ``data/raw/rules/``.
"""

from __future__ import annotations

import datetime as dt  # noqa: TC003
import uuid  # noqa: TC003
from decimal import Decimal  # noqa: TC003
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    column,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, RecordMixin

RULES_STATUSES = ("draft", "live", "retired")
GOING_RATE_TABLES = ("1", "1a", "2", "2a", "2aa", "2b", "3", "3a")
PAY_SCALE_TABLES = ("3", "3a", "4", "5")
SHORTAGE_LISTS = ("TSL", "ISL")
SALARY_OPTIONS = tuple("ABCDEFGHIJK")
APPLIES_TO = ("new", "transitional_pre_2024", "transitional_pre_jul_2025", "health_care")
NATIONS = ("England", "Scotland", "Wales", "Northern Ireland")

_CODE = "soc_code ~ '^[1-9][0-9]{3}$'"


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} in ({', '.join(repr(v) for v in values)})"


def _version_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        Uuid, ForeignKey("rules_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )


class RulesVersion(Base, RecordMixin):
    __tablename__ = "rules_versions"
    __table_args__ = (
        CheckConstraint(_in("status", RULES_STATUSES), name="status"),
        # At most one live version: the checker always reads that one.
        Index(
            "uq_rules_versions_one_live",
            "status",
            unique=True,
            postgresql_where=column("status") == "live",
        ),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="draft")
    # One entry per GOV.UK page: url, file, sha256, bytes, govuk_updated_at, retrieved_on.
    source_urls: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    # The latest GOV.UK "updated" date of the source pages.
    effective_from: Mapped[dt.date] = mapped_column(Date, nullable=False)
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT")
    )
    # Codes added/removed and rate changes against the version that was live at import time.
    diff_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # The notes printed under each table heading (pro-rating basis, hourly floors, who may use it).
    table_notes: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)


class GoingRate(Base, RecordMixin):
    """One row of Tables 1 to 3a. Money is null where the page says "Not applicable" or points to
    Table 4/5 (``notes`` then says which)."""

    __tablename__ = "going_rates"
    __table_args__ = (
        UniqueConstraint(
            "rules_version_id",
            "table",
            "soc_code",
            "administration",
            name="uq_going_rates_one_row",
        ),
        CheckConstraint(_CODE, name="soc_code"),
        CheckConstraint(_in('"table"', GOING_RATE_TABLES), name="table"),
    )

    rules_version_id: Mapped[uuid.UUID] = _version_fk()
    soc_code: Mapped[str] = mapped_column(String(4), nullable=False, index=True)
    table: Mapped[str] = mapped_column(String(3), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    # Table 3 lists some codes once per nation; empty text elsewhere, so the unique key works.
    administration: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    related_titles: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    soc2010_codes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    annual_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    hourly_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    rate_90: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    rate_80: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    rate_70: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    phd_points_eligible: Mapped[bool | None] = mapped_column(Boolean)
    basis_hours: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


class PayScaleRate(Base, RecordMixin):
    """A national pay-scale figure: a role inside a Table 3/3a cell (with its code), or a row of
    Table 4 (bands) or Table 5 (teacher roles), which apply to every code that points to them."""

    __tablename__ = "pay_scale_rates"
    __table_args__ = (
        CheckConstraint(_in("source_table", PAY_SCALE_TABLES), name="source_table"),
        CheckConstraint(f"soc_code is null or {_CODE}", name="soc_code"),
    )

    rules_version_id: Mapped[uuid.UUID] = _version_fk()
    source_table: Mapped[str] = mapped_column(String(2), nullable=False)
    soc_code: Mapped[str | None] = mapped_column(String(4), index=True)
    administration: Mapped[str] = mapped_column(Text, nullable=False)
    band_or_role: Mapped[str] = mapped_column(Text, nullable=False)
    annual_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    basis_hours: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))


class IneligibleCode(Base, RecordMixin):
    __tablename__ = "ineligible_codes"
    __table_args__ = (
        UniqueConstraint("rules_version_id", "soc_code", name="uq_ineligible_codes_one_code"),
        CheckConstraint(_CODE, name="soc_code"),
    )

    rules_version_id: Mapped[uuid.UUID] = _version_fk()
    soc_code: Mapped[str] = mapped_column(String(4), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    related_titles: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)


class ShortageListEntry(Base, RecordMixin):
    __tablename__ = "shortage_list_entries"
    __table_args__ = (
        UniqueConstraint("rules_version_id", "list", "soc_code", name="uq_shortage_list_one_code"),
        CheckConstraint(_CODE, name="soc_code"),
        CheckConstraint(_in("list", SHORTAGE_LISTS), name="list"),
    )

    rules_version_id: Mapped[uuid.UUID] = _version_fk()
    # Column "list" (plan 6.10); the attribute name keeps the builtin usable in this class.
    list_name: Mapped[str] = mapped_column("list", String(3), nullable=False)
    soc_code: Mapped[str] = mapped_column(String(4), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    # "all jobs", or the limit the list puts on the code (as published).
    condition_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    # TSL codes limited to listed job types ("only the following job types").
    job_types: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    nations: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    # ISL: the published removal date. TSL: the CoS must be issued before this date (SW 6.1A(b)).
    removal_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    # SW 29.1A: dependants only for a Table 1, 2 or 3 job (the engine handles transitional cases).
    dependants_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)


class SalaryRule(Base, RecordMixin):
    """One points option from the table after SW 4.4 of Appendix Skilled Worker."""

    __tablename__ = "salary_rules"
    __table_args__ = (
        UniqueConstraint("rules_version_id", "option", name="uq_salary_rules_one_option"),
        CheckConstraint(_in("option", SALARY_OPTIONS), name="option"),
        CheckConstraint(_in("applies_to", APPLIES_TO), name="applies_to"),
        CheckConstraint("going_rate_pct between 1 and 100", name="going_rate_pct"),
    )

    rules_version_id: Mapped[uuid.UUID] = _version_fk()
    option: Mapped[str] = mapped_column(String(1), nullable=False)
    general_threshold: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    going_rate_pct: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    criteria_key: Mapped[str] = mapped_column(String(20), nullable=False)
    applies_to: Mapped[str] = mapped_column(String(30), nullable=False)
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    further_rules: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
