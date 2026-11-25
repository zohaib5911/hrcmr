"""ISS-10 helpers: events that share one timestamp, and new events written between export pages."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    import pytest
    from sqlalchemy.ext.asyncio import AsyncEngine

INSERT = text(
    "insert into audit_events (id, company_id, actor_type, action, created_at) "
    "values (:i, :c, 'system', :a, :t)"
)


async def same_moment_events(
    owner: AsyncEngine, company: uuid.UUID | None, prefix: str, n: int
) -> list[str]:
    """``n`` events at one timestamp; returns their actions newest first (time, then id)."""
    moment = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [(uuid.uuid4(), f"{prefix}.{i}") for i in range(n)]
    async with owner.begin() as c:
        for ident, action in rows:
            await c.execute(INSERT, {"i": ident, "c": company, "a": action, "t": moment})
    return [action for _, action in sorted(rows, key=lambda row: row[0], reverse=True)]


def write_between_pages(
    monkeypatch: pytest.MonkeyPatch, owner: AsyncEngine, company: uuid.UUID | None, prefix: str
) -> None:
    """After every page read from audit_events, another request writes a newer event."""
    real = AsyncSession.execute

    async def execute(self: AsyncSession, statement: Any, *args: Any, **kwargs: Any) -> Any:
        result = await real(self, statement, *args, **kwargs)
        sql = str(statement)
        if "audit_events" in sql and "LIMIT" in sql:
            async with owner.begin() as c:
                await c.execute(
                    INSERT,
                    {
                        "i": uuid.uuid4(),
                        "c": company,
                        "a": f"{prefix}.late",
                        "t": datetime.now(UTC),
                    },
                )
        return result

    monkeypatch.setattr(AsyncSession, "execute", execute)
