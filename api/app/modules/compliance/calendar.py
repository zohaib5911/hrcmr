"""Reporting dates use the imported official regional calendar, never employee rota days."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.core.errors import AppError
from app.modules.companies.models import Company
from app.modules.compliance.working_days import add_working_days
from app.modules.holidays.models import BankHoliday

if TYPE_CHECKING:
    from datetime import date, datetime

    from app.modules.rbac.deps import Access


@dataclass(frozen=True)
class ReportingDeadline:
    deadline_date: date | None
    region: str
    checked_at: datetime | None
    holidays: tuple[date, ...]

    def fields(self) -> dict[str, object]:
        return {
            "deadline_date": self.deadline_date,
            "calendar_region": self.region,
            "calendar_checked_at": self.checked_at,
            "calendar_holidays": [day.isoformat() for day in self.holidays],
        }


def _unavailable() -> AppError:
    return AppError(
        "BANK_HOLIDAYS_UNAVAILABLE",
        "The official bank-holiday calendar does not cover these dates yet. "
        "Please try again later.",
        status_code=503,
    )


async def reporting_deadline(access: Access, event: date, days: int | None) -> ReportingDeadline:
    company = (
        await access.db.execute(select(Company).where(Company.id == access.company_id))
    ).scalar_one()
    region = company.bank_holiday_region
    if days is None:
        return ReportingDeadline(None, region, None, ())
    rows = (
        (await access.db.execute(select(BankHoliday).where(BankHoliday.region == region)))
        .scalars()
        .all()
    )
    years = {row.on_date.year for row in rows}
    if event.year not in years:
        raise _unavailable()
    holidays = frozenset(row.on_date for row in rows)
    deadline = add_working_days(event, days, holidays)
    needed = set(range(event.year, deadline.year + 1))
    if not needed <= years:
        raise _unavailable()
    checked = min(row.fetched_at for row in rows if row.on_date.year in needed)
    return ReportingDeadline(
        deadline, region, checked, tuple(sorted(day for day in holidays if event < day <= deadline))
    )
