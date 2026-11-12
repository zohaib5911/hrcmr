from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.register.geo import apply_companies_match, apply_geocoding, parse_places
from app.modules.register.models import Sponsor
from tests.db.support import DatabaseUnderTest, engine_for


async def test_geocoding_and_flagged_company_match(database: DatabaseUnderTest) -> None:
    engine = engine_for(database.owner_url)
    try:
        async with AsyncSession(engine) as db:
            for name, town in (("example care ltd", "leeds"), ("lost ltd", "atlantis")):
                db.add(
                    Sponsor(
                        organisation_name=name,
                        normalised_name=name,
                        town=town,
                        county="",
                        first_seen_on=date(2026, 11, 1),
                        last_seen_on=date(2026, 11, 1),
                        current=True,
                    )
                )
            await db.flush()
            places = parse_places(
                b"place_name,county,region,lat,lon\nLeeds,,Yorkshire and The Humber,53.8,-1.55\n"
            )
            assert await apply_geocoding(db, places) == 1
            assert await apply_geocoding(db, places) == 0  # only missing
            companies = {"example care ltd": ("01234567", "Q")}
            assert await apply_companies_match(db, companies, enabled=False) == 0
            assert await apply_companies_match(db, companies, enabled=True) == 1
            care = await db.scalar(select(Sponsor).where(Sponsor.town == "leeds"))
            assert care is not None
            assert (care.region_itl1, care.place_precision, care.sic_section) == (
                "Yorkshire and The Humber",
                "town",
                "Q",
            )
            await db.rollback()
    finally:
        await engine.dispose()
