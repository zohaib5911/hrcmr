"""T20.4: the public register pages. Regions, bulletins, profiles and sitemap ids read the global
snapshot tables; the report form is the only write and needs Turnstile and a per-connection limit."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.register import public as register
from app.modules.register.ingest import ingest
from tests.db.test_careers import anonymous
from tests.db.test_employee_documents import rig as rig
from tests.test_register_ingest import FIXTURES

API = "/api/v1/public/register"


async def _accept(token: str | None, remote_ip: str | None = None) -> bool:
    return True


async def _seed(rig: dict[str, Any]) -> None:
    current = "first.csv"

    def handler(request: httpx.Request) -> httpx.Response:
        name = current if request.url.path.endswith(".csv") else "publication.html"
        return httpx.Response(200, content=(FIXTURES / name).read_bytes())

    async with (
        AsyncSession(rig["owner"]) as db,
        httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client,
    ):
        await ingest(db, client, date(2026, 11, 10))
        current = "second.csv"
        await ingest(db, client, date(2026, 11, 11))
        await db.execute(text("update register_sponsors set region_itl1 = 'London'"))
        await db.commit()


async def _clear(rig: dict[str, Any]) -> None:
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "truncate register_problem_reports, register_possible_matches, register_changes, "
                "register_entries, register_sponsors, register_publications cascade"
            )
        )


@pytest.fixture(autouse=True)
async def clean(rig: dict[str, Any]) -> AsyncIterator[None]:
    await _clear(rig)
    yield
    await _clear(rig)


async def test_regions_bulletins_profiles_and_sitemap(rig: dict[str, Any]) -> None:
    await _seed(rig)
    public = anonymous(rig)
    listing = (await public.get(f"{API}/regions")).json()["regions"]
    assert len(listing) == 12
    london = (await public.get(f"{API}/regions/london")).json()
    assert london["region"] == "London"
    assert london["sponsors"] == 3
    assert (await public.get(f"{API}/regions/atlantis")).status_code == 404

    bulletins = (await public.get(f"{API}/changes")).json()["bulletins"]
    assert [b["date"] for b in bulletins] == ["2026-11-11", "2026-11-10"]
    day = (await public.get(f"{API}/changes/2026-11-11")).json()
    assert day["added"] == 2
    assert day["removed"] == 2
    assert day["net"] == 0
    assert day["median_added_last_28"] == 3.0
    assert len(day["possibly_same"]) == 1
    assert (await public.get(f"{API}/changes/2020-01-01")).status_code == 404

    first = day["added_list"][0]
    profile = (await public.get(f"{API}/sponsors/{first['stable_id']}")).json()
    assert profile["name"] == first["name"]
    assert profile["entries"]
    assert profile["changes"][0]["change"] == "added"
    assert (await public.get(f"{API}/sponsors/{'0' * 32}")).status_code == 404
    assert (await public.get(f"{API}/sponsors/not-an-id")).status_code == 422

    assert (await public.get(f"{API}/sitemap")).json() == {"pages": 1}
    ids = (await public.get(f"{API}/sitemap/0")).json()["items"]
    assert len(ids) == 5
    assert set(ids[0]) == {"stable_id", "slug", "last_seen_on"}
    await public.aclose()


async def test_the_report_form_needs_turnstile_and_is_limited(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    public = anonymous(rig)
    body = {"message": "Wrong town.", "turnstile_token": "t", "email": "A@Example.com"}

    async def refuse(token: str | None, remote_ip: str | None = None) -> bool:
        return False

    with monkeypatch.context() as patch:
        patch.setattr(rig["app"].state.auth.turnstile, "verify", refuse)
        assert (await public.post(f"{API}/reports", json=body)).status_code == 400
    monkeypatch.setattr(rig["app"].state.auth.turnstile, "verify", _accept)
    sent = await public.post(f"{API}/reports", json=body)
    assert sent.status_code == 201
    assert sent.json() == {"received": True}
    async with rig["owner"].connect() as connection:
        row = (await connection.execute(text("select email from register_problem_reports"))).one()
    assert row.email == "a@example.com"
    for _ in range(3):
        assert (await public.post(f"{API}/reports", json=body)).status_code == 201
    assert (await public.post(f"{API}/reports", json=body)).status_code == 429
    await public.aclose()


@pytest.mark.parametrize(
    "path",
    [
        "/regions",
        "/regions/london",
        "/changes",
        "/changes/2026-11-11",
        "/sponsors/{stable_id}",
        "/sitemap",
        "/sitemap/0",
        "/explore",
    ],
)
async def test_read_routes_share_a_connection_budget(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    await _seed(rig)
    async with rig["owner"].connect() as connection:
        stable_id = await connection.scalar(text("select stable_id from register_sponsors limit 1"))
    path = path.format(stable_id=stable_id)
    monkeypatch.setattr(register, "READ_PER_CONNECTION", ("public.register.read", 2, 60))
    async with (
        anonymous(rig) as public,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=rig["app"], client=("192.0.2.2", 12345)),
            base_url="http://test",
        ) as other,
    ):
        for _ in range(2):
            response = await public.get(f"{API}{path}")
            assert response.status_code == 200, response.text
        blocked = await public.get(f"{API}{path}")
        assert blocked.status_code == 429
        assert blocked.json()["error"]["code"] == "RATE_LIMITED"
        assert blocked.json()["error"]["request_id"]
        # Switching route families cannot bypass the shared budget.
        assert (await public.get(f"{API}/sitemap")).status_code == 429
        assert (await other.get(f"{API}{path}")).status_code == 200


async def test_explorer_retains_its_own_connection_limit(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(register, "SEARCH_PER_CONNECTION", ("public.search", 2, 60))
    async with anonymous(rig) as public:
        for _ in range(2):
            assert (await public.get(f"{API}/explore")).status_code == 200
        blocked = await public.get(f"{API}/explore")
        assert blocked.status_code == 429
        assert blocked.json()["error"]["code"] == "RATE_LIMITED"
        assert (await public.get(f"{API}/regions")).status_code == 200
