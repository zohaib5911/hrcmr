"""T4.5: the working pattern, bank holidays from GOV.UK, holiday types and company closures."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from app.core.crypto import KeyRing, set_keyring
from app.integrations.govuk_bank_holidays import FeedError, parse
from app.jobs.holidays import bank_holidays_weekly, import_bank_holidays
from app.main import create_app
from app.modules.auth.sessions import SessionStore
from tests.db.api_support import sign_in_as, two_companies
from tests.db.support import DatabaseUnderTest, engine_for
from tests.support import TEST_REDIS_URL, build_settings

FEED = {
    "england-and-wales": {
        "division": "england-and-wales",
        "events": [
            {"title": "New Year's Day", "date": "2026-01-01", "notes": "", "bunting": True},
            {"title": "Christmas Day", "date": "2026-12-25", "notes": "", "bunting": True},
        ],
    },
    "scotland": {
        "division": "scotland",
        "events": [
            {"title": "New Year's Day", "date": "2026-01-01", "notes": "", "bunting": True},
            {"title": "2nd January", "date": "2026-01-02", "notes": "", "bunting": True},
        ],
    },
    "northern-ireland": {
        "division": "northern-ireland",
        "events": [
            {"title": "St Patrick's Day", "date": "2026-03-17", "notes": "", "bunting": True}
        ],
    },
}


@pytest.fixture(autouse=True)
def _keys() -> Any:
    set_keyring(KeyRing(keys={"k1": os.urandom(32)}, active_kid="k1", blind_key=os.urandom(32)))
    yield
    set_keyring(None)


@pytest.fixture
async def rig(database: DatabaseUnderTest) -> AsyncIterator[dict[str, Any]]:
    redis = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    await redis.flushdb()
    a, b = await two_companies(database)
    owner = engine_for(database.owner_url, poolclass=NullPool)
    async with owner.begin() as c:
        await c.execute(text("truncate bank_holidays"))
    app = create_app(build_settings(database_url=database.app_url, redis_url=TEST_REDIS_URL))
    sessions = SessionStore(redis)
    clients: list[httpx.AsyncClient] = []

    async def person(role: str, company: uuid.UUID) -> httpx.AsyncClient:
        client = await sign_in_as(database, sessions, app, role, company)
        clients.append(client)
        return client

    async with LifespanManager(app):
        yield {"person": person, "a": a, "b": b, "db": database, "owner": owner}
    for client in clients:
        await client.aclose()
    await owner.dispose()
    await redis.flushdb()
    await redis.aclose()


def feed_client(payload: Any = FEED, status: int = 200) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(status, json=payload))
    )


def test_the_feed_is_read_strictly() -> None:
    parsed = parse(FEED)
    assert len(parsed) == 5
    assert {h.region for h in parsed} == {"england-and-wales", "scotland", "northern-ireland"}
    with pytest.raises(FeedError):
        parse({"england-and-wales": {"events": []}})
    with pytest.raises(FeedError):
        parse({**FEED, "scotland": {"events": [{"title": "x", "date": "not a date"}]}})


async def test_the_import_adds_and_updates_and_a_dead_feed_changes_nothing(
    rig: dict[str, Any],
) -> None:
    assert await import_bank_holidays(rig["owner"], feed_client()) == 5
    changed = {**FEED, "scotland": {"events": [{"title": "Renamed", "date": "2026-01-02"}]}}
    assert await import_bank_holidays(rig["owner"], feed_client(changed)) == 4  # 2 + 1 + 1
    async with rig["owner"].connect() as c:
        titles = {
            row[0]
            for row in await c.execute(
                text("select title from bank_holidays where region = 'scotland'")
            )
        }
        assert "Renamed" in titles
        total = (await c.execute(text("select count(*) from bank_holidays"))).scalar_one()
    assert total == 5  # re-importing the same date does not duplicate it

    assert (
        await bank_holidays_weekly({"owner_engine": rig["owner"], "http": feed_client(status=500)})
        == 0
    )
    assert await bank_holidays_weekly({"owner_engine": None}) == 0
    async with rig["owner"].connect() as c:
        assert (await c.execute(text("select count(*) from bank_holidays"))).scalar_one() == total


async def test_the_working_pattern_has_a_sensible_start_and_saves_what_is_sent(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    start = (await admin.get("/api/v1/working-pattern")).json()
    assert [d["is_working"] for d in start["days"]] == [True] * 5 + [False] * 2
    assert start["bank_holidays_non_working"] is True

    days = [
        {"weekday": d, "is_working": d in (1, 2, 3), "hours": "7.5" if d in (1, 2, 3) else "0"}
        for d in range(1, 8)
    ]
    saved = await admin.put(
        "/api/v1/working-pattern", json={"days": days, "bank_holidays_non_working": False}
    )
    assert saved.status_code == 200, saved.text
    again = (await admin.get("/api/v1/working-pattern")).json()
    assert [d["hours"] for d in again["days"]][:4] == ["7.50", "7.50", "7.50", "0.00"]
    assert again["bank_holidays_non_working"] is False
    # Saving the same thing records nothing more.
    await admin.put(
        "/api/v1/working-pattern", json={"days": days, "bank_holidays_non_working": False}
    )

    for bad in (
        {"days": days[:6], "bank_holidays_non_working": True},
        {"days": [{**d, "weekday": 1} for d in days], "bank_holidays_non_working": True},
        {"days": [{**days[0], "hours": "0"}, *days[1:]], "bank_holidays_non_working": True},
        {"days": [{**days[0], "hours": "30"}, *days[1:]], "bank_holidays_non_working": True},
    ):
        assert (await admin.put("/api/v1/working-pattern", json=bad)).status_code == 422


async def test_the_year_shows_bank_holidays_for_the_companys_region_and_its_closures(
    rig: dict[str, Any],
) -> None:
    await import_bank_holidays(rig["owner"], feed_client())
    admin = await rig["person"]("company_admin", rig["a"])
    empty = (await admin.get("/api/v1/holiday-management", params={"year": 2026})).json()
    assert empty["region"] == "england-and-wales"
    assert [b["title"] for b in empty["bank_holidays"]] == ["New Year's Day", "Christmas Day"]
    assert empty["bank_holidays_updated_at"] is not None

    kind = (
        await admin.post("/api/v1/holiday-types", json={"name": "Shutdown", "colour": "orange"})
    ).json()
    assert (await admin.post("/api/v1/holiday-types", json={"name": "SHUTDOWN"})).status_code == 409
    made = await admin.post(
        "/api/v1/company-holidays",
        json={
            "name": "Christmas shutdown",
            "start_date": "2026-12-24",
            "end_date": "2027-01-02",
            "holiday_type_id": kind["id"],
            "deduct_from_annual_leave": True,
        },
    )
    assert made.status_code == 201, made.text
    for year, expected in ((2026, 1), (2027, 1), (2025, 0), (2028, 0)):
        seen = (await admin.get("/api/v1/holiday-management", params={"year": year})).json()
        assert len(seen["company_holidays"]) == expected, year
    assert (await admin.get("/api/v1/holiday-management", params={"year": 1999})).status_code == 422

    # A type in use stays; changing the closure frees it.
    assert (await admin.delete(f"/api/v1/holiday-types/{kind['id']}")).status_code == 409
    moved = await admin.patch(
        f"/api/v1/company-holidays/{made.json()['id']}", json={"holiday_type_id": None}
    )
    assert moved.json()["holiday_type_id"] is None
    assert (await admin.delete(f"/api/v1/holiday-types/{kind['id']}")).status_code == 204
    assert (await admin.delete(f"/api/v1/company-holidays/{made.json()['id']}")).status_code == 204
    assert (await admin.get("/api/v1/holiday-management", params={"year": 2026})).json()[
        "company_holidays"
    ] == []

    bad = await admin.post(
        "/api/v1/company-holidays",
        json={"name": "Backwards", "start_date": "2026-05-05", "end_date": "2026-05-01"},
    )
    assert bad.status_code == 422


async def test_roles_other_companies_and_the_audit_trail(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    closure = (
        await admin.post(
            "/api/v1/company-holidays",
            json={"name": "Away day", "start_date": "2026-06-01", "end_date": "2026-06-01"},
        )
    ).json()
    manager = await rig["person"]("people_manager", rig["a"])
    assert (await manager.get("/api/v1/holiday-management")).status_code == 200
    assert (await manager.post("/api/v1/holiday-types", json={"name": "X"})).status_code == 403
    assert (
        await manager.post(
            "/api/v1/company-holidays",
            json={"name": "X", "start_date": "2026-06-01", "end_date": "2026-06-01"},
        )
    ).status_code == 403
    other = await rig["person"]("company_admin", rig["b"])
    seen = (await other.get("/api/v1/holiday-management", params={"year": 2026})).json()
    assert seen["company_holidays"] == []
    assert (await other.delete(f"/api/v1/company-holidays/{closure['id']}")).status_code == 404
    this_year = datetime.now(UTC).year
    assert (await admin.get("/api/v1/holiday-management")).json()["year"] in (
        this_year,
        this_year + 1,
        this_year - 1,
    )

    async with rig["owner"].connect() as c:
        rows = await c.execute(
            text(
                "select action from audit_events where company_id = :c "
                "and (action like 'company_holiday%' or action like 'holiday_type%' "
                "or action like 'working_pattern%') order by created_at"
            ),
            {"c": rig["a"]},
        )
        assert [r[0] for r in rows] == ["company_holiday.added"]


async def test_trading_hours_save_one_day_at_a_time_with_roles_isolation_and_audit(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    start = (await admin.get("/api/v1/trading-hours")).json()["days"]
    assert [d["weekday"] for d in start] == [1, 2, 3, 4, 5, 6, 7]
    assert not any(d["is_open"] for d in start)  # nothing is invented before it is set

    opened = {"is_open": True, "opens_at": "09:00", "closes_at": "17:30"}
    saved = await admin.put("/api/v1/trading-hours/1", json=opened)
    assert saved.status_code == 200, saved.text
    assert (await admin.put("/api/v1/trading-hours/1", json=opened)).status_code == 200  # no audit
    day = (await admin.get("/api/v1/trading-hours")).json()["days"][0]
    assert (day["is_open"], day["opens_at"], day["closes_at"]) == (True, "09:00:00", "17:30:00")
    closed = await admin.put(
        "/api/v1/trading-hours/1",
        json={"is_open": False, "opens_at": "09:00", "closes_at": "10:00"},
    )
    assert closed.json()["opens_at"] is None  # a closed day keeps no times

    for weekday, body in (
        (8, opened),
        (2, {"is_open": True}),
        (2, {"is_open": True, "opens_at": "17:00", "closes_at": "09:00"}),
        (2, {**opened, "extra": 1}),
    ):
        assert (await admin.put(f"/api/v1/trading-hours/{weekday}", json=body)).status_code == 422

    hr = await rig["person"]("hr_admin", rig["a"])
    assert (await hr.get("/api/v1/trading-hours")).status_code == 200
    assert (await hr.put("/api/v1/trading-hours/2", json=opened)).status_code == 403
    other = await rig["person"]("company_admin", rig["b"])
    assert not any(d["is_open"] for d in (await other.get("/api/v1/trading-hours")).json()["days"])

    async with rig["owner"].connect() as c:
        rows = await c.execute(
            text(
                "select action from audit_events where company_id = :c "
                "and action like 'trading_hours%' order by created_at"
            ),
            {"c": rig["a"]},
        )
        assert [r[0] for r in rows] == ["trading_hours.updated"] * 2  # opened, then closed


async def test_a_moved_future_holiday_replaces_its_old_date_and_history_stays(
    rig: dict[str, Any],
) -> None:
    """ISS-19: the feed's upcoming dates are reconciled; past dates and bad feeds change nothing."""
    from datetime import date

    today = date(2026, 6, 1)
    assert await import_bank_holidays(rig["owner"], feed_client(), today=today) == 5
    moved = {
        **FEED,
        "england-and-wales": {
            "events": [
                {"title": "New Year's Day", "date": "2026-01-01"},
                {"title": "Christmas Day", "date": "2026-12-28"},  # moved from the 25th
            ]
        },
        "northern-ireland": {"events": [{"title": "Boxing Day", "date": "2026-12-26"}]},
    }
    assert await import_bank_holidays(rig["owner"], feed_client(moved), today=today) == 5

    async def dates(region: str) -> list[str]:
        async with rig["owner"].connect() as c:
            rows = await c.execute(
                text("select on_date from bank_holidays where region = :r order by on_date"),
                {"r": region},
            )
            return [str(row[0]) for row in rows]

    assert await dates("england-and-wales") == ["2026-01-01", "2026-12-28"]
    assert await dates("northern-ireland") == ["2026-03-17", "2026-12-26"]  # March is history

    incomplete = {**moved, "scotland": {"events": []}}
    with pytest.raises(FeedError):
        await import_bank_holidays(rig["owner"], feed_client(incomplete), today=today)
    assert await dates("england-and-wales") == ["2026-01-01", "2026-12-28"]
