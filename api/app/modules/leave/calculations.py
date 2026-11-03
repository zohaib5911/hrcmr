"""Regular-pattern leave in standard company-day units; no database or clock dependencies.

A short personal day costs its hours / the company's average working-day hours.
Entitlement uses the same unit, so reduced hours are never pro-rated twice.
Employment end dates are inclusive; assignment ends are exclusive.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction
from itertools import pairwise
from math import ceil
from typing import Literal

ZERO = Decimal(0)
ONE = Decimal(1)
CENT = Decimal("0.01")


@dataclass(frozen=True)
class Pattern:
    start: date
    end: date | None
    hours: tuple[Decimal, ...]  # Monday through Sunday

    def __post_init__(self) -> None:
        if len(self.hours) != 7 or any(not h.is_finite() or h < 0 or h > 24 for h in self.hours):
            raise ValueError("A pattern needs seven finite daily hours from 0 to 24.")
        if self.end is not None and self.end <= self.start:
            raise ValueError("Pattern end must follow its start.")


def year_bounds(on: date, month_day: str) -> tuple[date, date]:
    month, day = map(int, month_day.split("-"))
    date(2001, month, day)  # Reject recurring February 29, even in a leap year.
    start = date(on.year, month, day)
    if start > on:
        start = date(on.year - 1, month, day)
    return start, date(start.year + 1, month, day)


def dates(start: date, end: date) -> list[date]:
    """Half-open interval, like assignment history and leave-year bounds."""
    return [start + timedelta(days=i) for i in range(max(0, (end - start).days))]


def hours_on(on: date, default: tuple[Decimal, ...], patterns: tuple[Pattern, ...]) -> Decimal:
    matching = [p for p in patterns if p.start <= on and (p.end is None or on < p.end)]
    if len(matching) > 1:
        raise ValueError("Working-pattern history overlaps.")
    return (matching[0].hours if matching else default)[on.weekday()]


def standard_day(default: tuple[Decimal, ...]) -> Decimal:
    Pattern(date(2001, 1, 1), None, default)
    working = sum(h > 0 for h in default)
    if not working:
        raise ValueError("Set at least one company working day before calculating leave.")
    return sum(default, ZERO) / working


def day_units(on: date, default: tuple[Decimal, ...], patterns: tuple[Pattern, ...]) -> Decimal:
    return hours_on(on, default, patterns) / standard_day(default)


def _month_boundary(start: date, offset: int) -> date:
    ordinal = start.year * 12 + start.month - 1 + offset
    year, month = divmod(ordinal, 12)
    return date(year, month + 1, min(start.day, calendar.monthrange(year, month + 1)[1]))


def entitlement(
    annual_days: Decimal | None,
    year_start: date,
    year_end: date,
    hire_date: date,
    leave_date: date | None,
    default: tuple[Decimal, ...],
    patterns: tuple[Pattern, ...] = (),
    *,
    method: Literal["front_loaded", "monthly"] = "front_loaded",
    as_of: date | None = None,
) -> Decimal | None:
    """Calendar-day pro-rata, rounded UP once to hundredths of a standard day.

    Monthly policy posts completed leave-months, with starters/leavers pro-rated
    within each month. Future months are not posted. Null allowance stays null.
    """
    if annual_days is None:
        return None
    if not annual_days.is_finite() or annual_days < 0 or year_end <= year_start:
        raise ValueError("Invalid entitlement or leave year.")
    standard_day(default)
    if leave_date is not None and leave_date < hire_date:
        raise ValueError("Leaving date precedes hire date.")
    if method == "monthly" and as_of is None:
        raise ValueError("Monthly accrual needs an as-of date.")
    start = max(year_start, hire_date)
    end = min(year_end, leave_date + timedelta(days=1) if leave_date else year_end)
    weekly = sum(default, ZERO)
    total = Fraction(0)
    for day in dates(start, end):
        # Evaluate the pattern effective ON this day for the whole weekly rate.
        active = [p for p in patterns if p.start <= day and (p.end is None or day < p.end)]
        if len(active) > 1:
            raise ValueError("Working-pattern history overlaps.")
        personal_week = sum(active[0].hours if active else default, ZERO)
        fraction = min(Fraction(1), Fraction(personal_week) / Fraction(weekly))
        if method == "monthly":
            boundaries = [_month_boundary(year_start, i) for i in range(13)]
            left, right = next(
                (left, right) for left, right in pairwise(boundaries) if left <= day < right
            )
            if as_of is None or right > as_of + timedelta(days=1):
                continue
            total += Fraction(annual_days) * fraction / 12 / (right - left).days
        else:
            total += Fraction(annual_days) * fraction / (year_end - year_start).days
    return Decimal(ceil(total * 100)) / 100


def calendar_deductions(
    start: date,
    end: date,
    hire_date: date,
    leave_date: date | None,
    default: tuple[Decimal, ...],
    patterns: tuple[Pattern, ...],
    bank_holidays: frozenset[date],
    closures: frozenset[date],
    *,
    bank_holidays_included: bool,
    bank_holidays_non_working: bool,
) -> Decimal:
    """Reserve once per scheduled day; overlapping bank holidays/closures never double-charge."""
    selected = closures | (
        bank_holidays if bank_holidays_included and bank_holidays_non_working else frozenset()
    )
    standard_day(default)
    hours = sum(
        (
            Fraction(hours_on(d, default, patterns))
            for d in selected
            if start <= d < end and d >= hire_date and (leave_date is None or d <= leave_date)
        ),
        Fraction(0),
    )
    total = hours * sum(h > 0 for h in default) / Fraction(sum(default, ZERO))
    return Decimal(ceil(total * 100)) / 100
