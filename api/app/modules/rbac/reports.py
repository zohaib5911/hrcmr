"""Who reports to whom (plan.md 7.3 and 8.3).

A person with a ``_reports`` permission acts on their direct and indirect reports. Two chains exist:
the Reporting Authority (line manager) and the Leave Sanctioning Authority. Both are columns on the
``employees`` table (T4), and are walked here with one recursive query.

The query is written against the columns by name, not against the employees model, because the model
arrives in Phase 4; it works unchanged once that table has these columns. Row-Level Security applies
(the session is a tenant session) and the company is also named in the query.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from typing import TYPE_CHECKING, Literal

from sqlalchemy import Uuid, column, select, table

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

Relation = Literal["reporting", "leave"]

_EMPLOYEES = table(
    "employees",
    column("id", Uuid),
    column("company_id", Uuid),
    column("reporting_authority_employee_id", Uuid),
    column("leave_sanctioning_employee_id", Uuid),
)
_COLUMN_FOR: dict[str, str] = {
    "reporting": "reporting_authority_employee_id",
    "leave": "leave_sanctioning_employee_id",
}


class ReportsGraph:
    """The reports of managers in one company, looked up once per request and remembered."""

    def __init__(self, db: AsyncSession, company_id: uuid.UUID) -> None:
        self._db = db
        self._company_id = company_id
        self._cache: dict[tuple[str, uuid.UUID], frozenset[uuid.UUID]] = {}

    async def reports_of(
        self, manager_id: uuid.UUID, relation: Relation = "reporting"
    ) -> frozenset[uuid.UUID]:
        """Everyone below ``manager_id``, at any depth. Never includes the manager."""
        key = (relation, manager_id)
        if key not in self._cache:
            link = _EMPLOYEES.c[_COLUMN_FOR[relation]]
            chain = (
                select(_EMPLOYEES.c.id)
                .where(link == manager_id, _EMPLOYEES.c.company_id == self._company_id)
                .cte("chain", recursive=True)
            )
            # UNION (not UNION ALL) drops repeated rows, so a loop in the data (A reports to B and B
            # to A) ends instead of running forever.
            chain = chain.union(
                select(_EMPLOYEES.c.id).where(
                    link == chain.c.id, _EMPLOYEES.c.company_id == self._company_id
                )
            )
            rows = await self._db.execute(select(chain.c.id))
            self._cache[key] = frozenset(rows.scalars()) - {manager_id}
        return self._cache[key]

    async def is_report(
        self, manager_id: uuid.UUID, employee_id: uuid.UUID, relation: Relation = "reporting"
    ) -> bool:
        return employee_id in await self.reports_of(manager_id, relation)
