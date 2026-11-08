"""Remove one company's rows from every tenant table (T16.5, the account deletion executor).

Runs as the table owner (outside Row-Level Security), in one transaction. The history tables
refuse DELETE in a trigger; migration 0047 lets a DELETE through only when the connecting role is
the owner AND this transaction named the same company in ``app.purge_company_id``
(``mark_purge``). Nothing else sets that setting.

Kept: the company row itself (emptied by the caller), its ``subscriptions`` (payment records the
law requires) and its ``deletion_requests`` (the record that the account was deleted).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

from app.db.base import Base

if TYPE_CHECKING:
    import uuid

    from sqlalchemy import Table
    from sqlalchemy.ext.asyncio import AsyncSession

KEPT_TABLES = frozenset({"subscriptions", "deletion_requests"})
_MARK = text("select set_config('app.purge_company_id', :company_id, true)")


def purged_tables() -> list[Table]:
    """Every table holding company rows, children before the tables they point at."""
    return [
        table
        for table in reversed(Base.metadata.sorted_tables)
        if "company_id" in table.c and table.name not in KEPT_TABLES
    ]


async def mark_purge(db: AsyncSession, company_id: uuid.UUID) -> None:
    """Allow this transaction (only) to delete ``company_id``'s history rows."""
    await db.execute(_MARK, {"company_id": str(company_id)})


async def delete_company_rows(db: AsyncSession, company_id: uuid.UUID) -> dict[str, int]:
    """Deletes the rows, table by table. Returns how many went from each (non-empty) table."""
    await mark_purge(db, company_id)
    counts: dict[str, int] = {}
    for table in purged_tables():
        result = await db.execute(table.delete().where(table.c["company_id"] == company_id))
        if result.rowcount:  # type: ignore[attr-defined]
            counts[table.name] = int(result.rowcount)  # type: ignore[attr-defined]
    return counts
