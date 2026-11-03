"""Frozen official regional holidays for deadline/browser tests, checked 2026-11-03.

Source: https://www.gov.uk/bank-holidays (2026 and 2027). Runtime code continues to use the
weekly GOV.UK import; browser tests have no background worker or external network dependency.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from sqlalchemy.dialects.postgresql import insert

from app.integrations.govuk_bank_holidays import SOURCE_URL
from app.modules.holidays.models import BankHoliday

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

COMMON = [
    ("2026-01-01", "New Year's Day"),
    ("2026-04-03", "Good Friday"),
    ("2026-05-04", "Early May bank holiday"),
    ("2026-05-25", "Spring bank holiday"),
    ("2026-12-25", "Christmas Day"),
    ("2026-12-28", "Boxing Day (substitute day)"),
    ("2027-01-01", "New Year's Day"),
    ("2027-03-26", "Good Friday"),
    ("2027-05-03", "Early May bank holiday"),
    ("2027-05-31", "Spring bank holiday"),
    ("2027-12-27", "Christmas Day (substitute day)"),
    ("2027-12-28", "Boxing Day (substitute day)"),
]
EXTRA = {
    "england-and-wales": [
        ("2026-04-06", "Easter Monday"),
        ("2026-08-31", "Summer bank holiday"),
        ("2027-03-29", "Easter Monday"),
        ("2027-08-30", "Summer bank holiday"),
    ],
    "scotland": [
        ("2026-01-02", "2nd January"),
        ("2026-06-15", "World Cup bank holiday"),
        ("2026-08-03", "Summer bank holiday"),
        ("2026-11-30", "St Andrew's Day"),
        ("2027-01-04", "2nd January (substitute day)"),
        ("2027-08-02", "Summer bank holiday"),
        ("2027-11-30", "St Andrew's Day"),
    ],
    "northern-ireland": [
        ("2026-03-17", "St Patrick's Day"),
        ("2026-04-06", "Easter Monday"),
        ("2026-07-13", "Battle of the Boyne (substitute day)"),
        ("2026-08-31", "Summer bank holiday"),
        ("2027-03-17", "St Patrick's Day"),
        ("2027-03-29", "Easter Monday"),
        ("2027-07-12", "Battle of the Boyne"),
        ("2027-08-30", "Summer bank holiday"),
    ],
}


async def seed_reporting_calendar(engine: AsyncEngine) -> None:
    now = datetime.now(UTC)
    rows = [
        {
            "region": region,
            "on_date": date.fromisoformat(day),
            "title": title,
            "source": SOURCE_URL,
            "fetched_at": now,
        }
        for region, extra in EXTRA.items()
        for day, title in [*COMMON, *extra]
    ]
    async with engine.begin() as connection:
        await connection.execute(
            insert(BankHoliday)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["region", "on_date"])
        )
