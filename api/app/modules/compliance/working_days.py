"""Sponsor reporting working days, checked against GOV.UK on 2026-11-03.

The sponsor glossary excludes Saturdays, Sundays and UK bank holidays. Part 3 C1.13/C2.3
counts after the relevant event (or awareness date for organisation changes). The caller supplies
holidays for the company's region, independently of its personal/rota working pattern.

https://www.gov.uk/government/publications/workers-and-temporary-workers-guidance-for-sponsors-glossary/workers-and-temporary-workers-guidance-for-sponsors-glossary-accessible#working-days
https://www.gov.uk/government/publications/workers-and-temporary-workers-guidance-for-sponsors-part-3-sponsor-duties-and-compliance/workers-and-temporary-workers-guidance-for-sponsors-part-3-sponsor-duties-and-compliance-accessible
https://www.gov.uk/bank-holidays
"""

from __future__ import annotations

from collections.abc import Collection  # noqa: TC003
from datetime import date, timedelta


def is_working_day(day: date, bank_holidays: Collection[date]) -> bool:
    return day.weekday() < 5 and day not in bank_holidays


def add_working_days(event_date: date, days: int, bank_holidays: Collection[date]) -> date:
    """Exclude the event date; include the last counted working day. Zero leaves the date alone."""
    if days < 0:
        raise ValueError("The number of working days cannot be negative.")
    day = event_date
    remaining = days
    while remaining:
        day += timedelta(days=1)
        if is_working_day(day, bank_holidays):
            remaining -= 1
    return day


def working_days_between(start: date, end: date, bank_holidays: Collection[date]) -> int:
    """Working days in (start, end], signed when reversed. Calendar dates decide overdue status."""
    if end < start:
        return -working_days_between(end, start, bank_holidays)
    day = start
    total = 0
    while day < end:
        day += timedelta(days=1)
        total += int(is_working_day(day, bank_holidays))
    return total
