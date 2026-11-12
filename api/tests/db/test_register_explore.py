"""Snapshot queries use public tables and count sponsors once across multiple routes."""

from datetime import date

import httpx
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import GlobalSession
from app.modules.register.ingest import ingest
from app.modules.register.models import Sponsor
from app.modules.register.public import ExploreQuery, explore_data
from tests.db.support import DatabaseUnderTest, engine_for
from tests.test_register_ingest import FIXTURES


async def test_explore_snapshots_filters_counts_and_pulse(database: DatabaseUnderTest) -> None:
    engine = engine_for(database.owner_url)
    reader = engine_for(database.app_url)
    fixture = "first.csv"

    def handler(request: httpx.Request) -> httpx.Response:
        name = fixture if request.url.path.endswith(".csv") else "publication.html"
        return httpx.Response(200, content=(FIXTURES / name).read_bytes())

    try:
        async with (
            AsyncSession(engine) as db,
            httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client,
        ):
            await ingest(db, client, date(2026, 11, 10))
            fixture = "second.csv"
            await ingest(db, client, date(2026, 11, 11))
            await db.execute(
                update(Sponsor)
                .where(Sponsor.town == "leeds")
                .values(
                    region_itl1="Yorkshire and The Humber", sic_section="J", place_precision="town"
                )
            )
            await db.commit()
        async with GlobalSession(reader) as db:
            out = await explore_data(db, ExploreQuery(window="start"))
            assert out.total == out.previous_total == 3
            assert len(out.results) == 3  # four entries, three sponsors
            assert out.timeline[-1].added == 2
            assert out.timeline[-1].removed == 2
            assert out.timeline[0].added == 3
            assert out.sections["types"][0].count == 3
            assert out.sections["routes"][0].count == 3
            assert len(out.facets["route"]) == 2
            stable = next(s for s in out.results if s.name == "Stable Ltd")
            assert len(stable.routes) == len(stable.ratings) == 2
            historic = await explore_data(db, ExploreQuery(publication_id=out.publications[0].id))
            assert historic.total == 3
            assert "Gone Ltd" in {s.name for s in historic.results}
            assert "Worker (B rating)" not in {r for s in historic.results for r in s.ratings}
            for query in (
                ExploreQuery(q="leeds"),
                ExploreQuery(q="Global Business"),
                ExploreQuery(region="Yorkshire and The Humber"),
                ExploreQuery(route="Global Business Mobility"),
                ExploreQuery(rating="Worker (B rating)"),
                ExploreQuery(industry="J"),
            ):
                filtered = await explore_data(db, query)
                assert filtered.total == 1
                assert filtered.results[0].name == "Stable Ltd"
            assert (await explore_data(db, ExploreQuery(q="%"))).total == 0
            assert (await explore_data(db, ExploreQuery(q="absent"))).results == []
            assert (await explore_data(db, ExploreQuery(page=2))).results == []
            assert (
                await explore_data(db, ExploreQuery(published_on=date(2000, 1, 1)))
            ).selected is None
    finally:
        # This fixture's register tables are global; leave the shared database clean.
        from sqlalchemy import text

        async with engine.begin() as connection:
            await connection.execute(
                text("TRUNCATE register_publications, register_sponsors CASCADE")
            )
        await reader.dispose()
        await engine.dispose()
