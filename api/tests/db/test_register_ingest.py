from datetime import UTC, date, datetime

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.register import register_ingest
from app.modules.register.ingest import ingest
from app.modules.register.models import Change, Entry, PossibleMatch, Publication, Sponsor
from tests.db.support import DatabaseUnderTest, engine_for
from tests.test_register_ingest import FIXTURES


async def test_snapshots_idempotency_diff_return_and_rollback(database: DatabaseUnderTest) -> None:
    engine = engine_for(database.owner_url)
    fixture = "first.csv"

    def handler(request: httpx.Request) -> httpx.Response:
        content = (
            FIXTURES / (fixture if request.url.path.endswith(".csv") else "publication.html")
        ).read_bytes()
        return httpx.Response(200, content=content)

    try:
        async with (
            AsyncSession(engine) as db,
            httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client,
        ):
            assert await ingest(db, client, date(2026, 11, 10)) == "imported"
            assert await ingest(db, client, date(2026, 11, 10)) == "unchanged"
            assert await db.scalar(select(func.count()).select_from(Publication)) == 1
            fixture = "second.csv"
            assert await ingest(db, client, date(2026, 11, 11)) == "imported"
            assert await db.scalar(select(func.count()).select_from(Publication)) == 2
            kinds = list((await db.scalars(select(Change.change))).all())
            assert kinds.count("removed") == 2
            assert kinds.count("added") == 5
            assert kinds.count("rating_changed") == 1
            assert kinds.count("route_added") == 1
            assert await db.scalar(select(func.count()).select_from(PossibleMatch)) == 1
            assert await db.scalar(select(func.count()).select_from(Entry)) == 7
            assert (
                await db.scalar(select(func.count()).select_from(Sponsor).where(Sponsor.current))
                == 3
            )
            # Rollback includes publication, entries, sponsor flags and diffs together.
            await db.rollback()
            assert await db.scalar(select(func.count()).select_from(Publication)) == 0
            assert (
                await register_ingest(
                    {
                        "now": datetime(2026, 7, 13, 9, tzinfo=UTC),
                        "owner_engine": engine,
                        "http": client,
                    }
                )
                == "imported"
            )
    finally:
        await engine.dispose()
