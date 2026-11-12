import asyncio
from datetime import UTC, date, datetime

import httpx
from sqlalchemy import func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from app.cli import alembic_config
from app.jobs.register import register_ingest
from app.jobs.scheduled import functions
from app.modules.register.ingest import ingest
from app.modules.register.models import Change, Entry, PossibleMatch, Publication, Sponsor
from tests.db.support import DatabaseUnderTest, engine_for, temporary_database
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
            fixture = "first.csv"
            assert await ingest(db, client, date(2026, 11, 12)) == "imported"
            kinds = list((await db.scalars(select(Change.change))).all())
            assert kinds.count("returned") == 2
            assert kinds.count("route_removed") == 1
            assert kinds.count("removed") == 4
            publications = list(
                (await db.scalars(select(Publication).order_by(Publication.id))).all()
            )
            assert len(publications) == 3
            assert publications[0].sha256 == publications[2].sha256
            assert publications[0].sha256 != publications[1].sha256
            assert set(
                (await db.scalars(select(Sponsor.organisation_name).where(Sponsor.current))).all()
            ) == {"Example Care Ltd", "Stable Ltd", "Gone Ltd"}
            assert await db.scalar(select(func.count()).select_from(Entry)) == 10
            assert await ingest(db, client, date(2026, 11, 13)) == "unchanged"
            assert await db.scalar(select(func.count()).select_from(Publication)) == 3
            assert await db.scalar(select(func.count()).select_from(Entry)) == 10
            assert len((await db.scalars(select(Change))).all()) == len(kinds)
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
            # Manual worker registration actually imports on a weekend, outside cron hours.
            manual = next(f for f in functions() if f.name == "rerun_register_ingest")
            assert (
                await manual.coroutine(
                    {
                        "now": datetime(2026, 11, 14, 2, tzinfo=UTC),
                        "owner_engine": engine,
                        "http": client,
                    }
                )
                == "unchanged"
            )
    finally:
        await engine.dispose()


def test_hash_history_migration_from_unique_constraint(stack: None) -> None:
    async def hash_schema(database: DatabaseUnderTest) -> tuple[bool, bool]:
        engine = engine_for(database.owner_url)
        try:
            async with engine.connect() as connection:
                constraints, indexes = await connection.run_sync(
                    lambda conn: (
                        inspect(conn).get_unique_constraints("register_publications"),
                        inspect(conn).get_indexes("register_publications"),
                    )
                )
                return (
                    any(c["column_names"] == ["sha256"] for c in constraints),
                    any(i["column_names"] == ["sha256"] and not i["unique"] for i in indexes),
                )
        finally:
            await engine.dispose()

    with temporary_database() as database:
        config = alembic_config(database.owner_url)
        command.downgrade(config, "0060_register_rerun")
        assert asyncio.run(hash_schema(database)) == (True, False)
        command.upgrade(config, "head")
        assert asyncio.run(hash_schema(database)) == (False, True)
