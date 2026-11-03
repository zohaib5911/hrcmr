"""T8.2: independently worked regular-pattern entitlement and calendar cases."""

from datetime import date
from decimal import Decimal

import pytest

from app.modules.leave.calculations import (
    Pattern,
    calendar_deductions,
    day_units,
    entitlement,
    year_bounds,
)

FULL = tuple(map(Decimal, ("8", "8", "8", "8", "8", "0", "0")))
THREE = tuple(map(Decimal, ("8", "8", "8", "0", "0", "0", "0")))
SHORT = tuple(map(Decimal, ("4", "4", "4", "4", "4", "0", "0")))
START = date(2026, 1, 1)
END = date(2027, 1, 1)


def amount(
    *,
    hire: date = START,
    leave: date | None = None,
    patterns: tuple[Pattern, ...] = (),
    start: date = START,
    end: date = END,
    days: Decimal | None = Decimal(28),
    method: str = "front_loaded",
    as_of: date | None = None,
) -> Decimal | None:
    if method == "monthly":
        return entitlement(
            days, start, end, hire, leave, FULL, patterns, method="monthly", as_of=as_of
        )
    return entitlement(days, start, end, hire, leave, FULL, patterns)


@pytest.mark.parametrize(
    ("on", "setting", "expected"),
    [
        (date(2026, 1, 1), "01-01", (START, END)),
        (date(2026, 4, 5), "04-06", (date(2025, 4, 6), date(2026, 4, 6))),
        (date(2026, 4, 6), "04-06", (date(2026, 4, 6), date(2027, 4, 6))),
        (date(2026, 12, 31), "01-01", (START, END)),
    ],
)
def test_leave_year_boundaries(on: date, setting: str, expected: tuple[date, date]) -> None:
    assert year_bounds(on, setting) == expected


@pytest.mark.parametrize("setting", ["02-29", "04-31", "00-01", "13-01"])
def test_invalid_recurring_dates(setting: str) -> None:
    with pytest.raises(ValueError, match=r"out of range|month must be"):
        year_bounds(date(2028, 3, 1), setting)


@pytest.mark.parametrize(
    ("hire", "leave", "expected"),
    [
        (START, None, Decimal("28")),
        (date(2026, 7, 1), None, Decimal("14.12")),  # 28 * 184 / 365, rounded up
        (START, date(2026, 6, 30), Decimal("13.89")),  # 28 * 181 / 365
        (date(2026, 7, 1), date(2026, 7, 1), Decimal(".08")),
        (END, None, Decimal(0)),
        (date(2025, 1, 1), date(2025, 12, 31), Decimal(0)),
    ],
)
def test_starters_leavers_inclusive_and_outside_year(
    hire: date, leave: date | None, expected: Decimal
) -> None:
    assert amount(hire=hire, leave=leave) == expected


def test_leap_year_and_custom_year() -> None:
    assert amount(start=date(2028, 1, 1), end=date(2029, 1, 1), hire=date(2028, 7, 1)) == Decimal(
        "14.08"
    )
    assert amount(start=date(2025, 4, 6), end=date(2026, 4, 6), hire=date(2025, 4, 6)) == Decimal(
        28
    )


def test_null_allowance_is_not_zero_or_automatic_entitlement() -> None:
    assert amount(days=None) is None
    assert amount(days=Decimal(0)) == Decimal(0)


def test_three_day_gov_example_and_short_days_use_consistent_units() -> None:
    assert amount(patterns=(Pattern(START, None, THREE),)) == Decimal("16.8")
    short = (Pattern(START, None, SHORT),)
    assert amount(patterns=short) == Decimal(14)
    assert day_units(date(2026, 1, 5), FULL, short) == Decimal(".5")
    assert day_units(date(2026, 1, 10), FULL, short) == Decimal(0)


def test_assignment_changes_apply_on_effective_date_and_do_not_rewrite_past() -> None:
    patterns = (Pattern(START, date(2026, 7, 1), FULL), Pattern(date(2026, 7, 1), None, THREE))
    assert amount(patterns=patterns) == Decimal("22.36")  # (28*181 + 16.8*184)/365
    assert day_units(date(2026, 6, 25), FULL, patterns) == Decimal(1)
    assert day_units(date(2026, 7, 2), FULL, patterns) == Decimal(0)


@pytest.mark.parametrize(
    ("as_of", "expected"),
    [
        (date(2025, 12, 31), "0"),
        (date(2026, 1, 30), "0"),
        (date(2026, 1, 31), "2.34"),
        (date(2026, 3, 31), "7"),
        (date(2026, 12, 31), "28"),
    ],
)
def test_monthly_completed_periods_and_exact_decimal_totals(as_of: date, expected: str) -> None:
    assert amount(method="monthly", as_of=as_of) == Decimal(expected)


def test_monthly_partial_starter_and_non_first_day_year() -> None:
    assert amount(method="monthly", as_of=date(2026, 1, 31), hire=date(2026, 1, 13)) == Decimal(
        "1.44"
    )
    assert amount(
        method="monthly",
        as_of=date(2026, 5, 5),
        start=date(2026, 4, 6),
        end=date(2027, 4, 6),
        hire=date(2026, 4, 6),
    ) == Decimal("2.34")


def test_bank_holidays_personal_days_closures_and_overlap() -> None:
    # Monday and Thursday holidays; only Monday is in this person's three-day week.
    bank = frozenset({date(2026, 1, 5), date(2026, 1, 8)})
    closures = frozenset({date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 10)})
    args = (START, END, START, None, FULL, (Pattern(START, None, THREE),), bank, closures)
    assert calendar_deductions(
        *args, bank_holidays_included=True, bank_holidays_non_working=True
    ) == Decimal(2)
    assert calendar_deductions(
        *args, bank_holidays_included=False, bank_holidays_non_working=True
    ) == Decimal(2)
    assert calendar_deductions(
        START,
        END,
        START,
        None,
        FULL,
        (),
        bank,
        frozenset(),
        bank_holidays_included=True,
        bank_holidays_non_working=False,
    ) == Decimal(0)


def test_deductions_clip_to_employment_year_and_short_day_hours() -> None:
    bank = frozenset(
        {date(2025, 12, 31), date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7), END}
    )
    assert calendar_deductions(
        START,
        END,
        date(2026, 1, 6),
        date(2026, 1, 6),
        FULL,
        (Pattern(START, None, SHORT),),
        bank,
        frozenset(),
        bank_holidays_included=True,
        bank_holidays_non_working=True,
    ) == Decimal(".5")


def test_invalid_patterns_and_overlapping_history_fail_explicitly() -> None:
    with pytest.raises(ValueError, match="seven finite"):
        Pattern(START, None, (Decimal(8),))
    with pytest.raises(ValueError, match="overlaps"):
        amount(patterns=(Pattern(START, None, FULL), Pattern(START, None, THREE)))
    with pytest.raises(ValueError, match="at least one"):
        entitlement(Decimal(28), START, END, START, None, (Decimal(0),) * 7)
    with pytest.raises(ValueError, match="precedes"):
        amount(hire=END, leave=START)
    with pytest.raises(ValueError, match="as-of"):
        amount(method="monthly")
