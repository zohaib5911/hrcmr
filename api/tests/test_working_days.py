"""Examples derived from the regional dates on https://www.gov.uk/bank-holidays (2026-11-03).

The expected deadlines are our calculation of the official working-day rule, not quoted
Home Office worked examples. Reporting periods are in sponsor Part 3 C1.13/C2.3.
"""

from datetime import date

import pytest

from app.modules.compliance.working_days import add_working_days, working_days_between

D = date.fromisoformat


@pytest.mark.parametrize(
    ("event", "days", "holidays", "expected"),
    [
        # Friday before the England/Wales summer bank holiday Monday (plan Phase 7 scenario).
        ("2026-08-28", 10, ["2026-08-31"], "2026-09-14"),
        ("2026-08-28", 20, ["2026-08-31"], "2026-09-28"),
        # Scotland's summer holiday is the first Monday in August, not the last.
        ("2026-07-31", 10, ["2026-08-03"], "2026-08-17"),
        ("2026-07-31", 10, [], "2026-08-14"),
        # Northern Ireland: St Patrick's Day (Tuesday); other regions do not exclude it.
        ("2026-03-13", 10, ["2026-03-17"], "2026-03-30"),
        ("2026-03-13", 10, [], "2026-03-27"),
        # Good Friday and Easter Monday in England/Wales; Scotland excludes only Good Friday.
        ("2026-04-02", 10, ["2026-04-03", "2026-04-06"], "2026-04-20"),
        ("2026-04-02", 10, ["2026-04-03"], "2026-04-17"),
        # Boxing Day falls on Saturday: the official substitute date is Monday 28 December.
        ("2026-12-24", 10, ["2026-12-25", "2026-12-28", "2027-01-01"], "2027-01-12"),
        ("2026-08-29", 1, ["2026-08-31"], "2026-09-01"),
        ("2026-08-29", 0, [], "2026-08-29"),
    ],
)
def test_reporting_deadlines_from_official_holiday_dates(
    event: str, days: int, holidays: list[str], expected: str
) -> None:
    dates = frozenset(D(day) for day in holidays)
    assert add_working_days(D(event), days, dates) == D(expected)
    assert working_days_between(D(event), D(expected), dates) == days


def test_remaining_days_count_the_deadline_and_are_signed() -> None:
    holidays = {D("2026-08-31")}
    assert working_days_between(D("2026-08-28"), D("2026-09-01"), holidays) == 1
    assert working_days_between(D("2026-09-01"), D("2026-08-28"), holidays) == -1
    assert working_days_between(D("2026-09-01"), D("2026-09-01"), holidays) == 0
    assert working_days_between(D("2026-09-04"), D("2026-09-05"), holidays) == 0
    with pytest.raises(ValueError, match="negative"):
        add_working_days(D("2026-09-01"), -1, holidays)
