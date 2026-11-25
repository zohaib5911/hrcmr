"""Who reports to whom (plan.md 7.3 and 8.3).

A person with a ``_reports`` permission acts on their direct and indirect reports. Two chains exist:
the Reporting Authority (line manager) and the Leave Sanctioning Authority. Both are columns on the
employee's assignment effective today (plan 6.3), and are walked
here with one recursive query. "Today" is the company's local date, worked out once per request
(ISS-06): the database session's own date is UTC and would move a hand-over at local midnight.

The query is written against the columns by name rather than the model. Row-Level Security applies
(the session is a tenant session) and the company is also named in the query.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import Date, String, Uuid, column, literal, select, table

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncSession

Relation = Literal["reporting", "leave"]

_EMPLOYEES = table(
    "employee_assignments",
    column("employee_id", Uuid),
    column("company_id", Uuid),
    column("ended_at", Date),
    column("effective_from", Date),
    column("reporting_authority_employee_id", Uuid),
    column("leave_sanctioning_employee_id", Uuid),
)
_COMPANIES = table("companies", column("id", Uuid), column("timezone", String))
_COLUMN_FOR: dict[str, str] = {
    "reporting": "reporting_authority_employee_id",
    "leave": "leave_sanctioning_employee_id",
}


class ReportsGraph:
    """The reports of managers in one company, looked up once per request and remembered."""

    def __init__(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._db = db
        self._company_id = company_id
        self._clock = clock
        self._today: date | None = None
        self._cache: dict[tuple[str, uuid.UUID], frozenset[uuid.UUID]] = {}

    async def today(self) -> date:
        """The company's local date, resolved once and used for every query of this request."""
        if self._today is None:
            zone = await self._db.scalar(
                select(_COMPANIES.c.timezone).where(_COMPANIES.c.id == self._company_id)
            )
            self._today = self._clock().astimezone(ZoneInfo(zone or "Europe/London")).date()
        return self._today

    async def reports_of(
        self, manager_id: uuid.UUID, relation: Relation = "reporting"
    ) -> frozenset[uuid.UUID]:
        """Everyone below ``manager_id``, at any depth. Never includes the manager."""
        key = (relation, manager_id)
        if key not in self._cache:
            link = _EMPLOYEES.c[_COLUMN_FOR[relation]]
            today = literal(await self.today(), Date)
            chain = (
                select(_EMPLOYEES.c.employee_id.label("id"))
                .where(
                    link == manager_id,
                    _EMPLOYEES.c.company_id == self._company_id,
                    _EMPLOYEES.c.effective_from <= today,
                    (_EMPLOYEES.c.ended_at.is_(None) | (_EMPLOYEES.c.ended_at > today)),
                )
                .cte("chain", recursive=True)
            )
            # UNION (not UNION ALL) drops repeated rows, so a loop in the data (A reports to B and B
            # to A) ends instead of running forever.
            chain = chain.union(
                select(_EMPLOYEES.c.employee_id).where(
                    link == chain.c.id,
                    _EMPLOYEES.c.company_id == self._company_id,
                    _EMPLOYEES.c.effective_from <= today,
                    (_EMPLOYEES.c.ended_at.is_(None) | (_EMPLOYEES.c.ended_at > today)),
                )
            )
            rows = await self._db.execute(select(chain.c.id))
            self._cache[key] = frozenset(rows.scalars()) - {manager_id}
        return self._cache[key]

    async def is_report(
        self, manager_id: uuid.UUID, employee_id: uuid.UUID, relation: Relation = "reporting"
    ) -> bool:
        return employee_id in await self.reports_of(manager_id, relation)
