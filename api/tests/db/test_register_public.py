"""T20.4: the public register pages. Regions, bulletins, profiles and sitemap ids read the global
snapshot tables; the report form is the only write and needs Turnstile and a per-connection limit."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app import cli
from app.jobs.register import register_ingest_manual
from app.modules.register import public as register
from app.modules.register.ingest import ingest
from app.modules.register.models import CompanyDataset, CompanyMatch, Sponsor
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
                "register_entries, register_sponsors, register_publications, "
                "register_place_datasets, register_company_matches, register_company_datasets cascade"
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


async def _ingest(rig: dict[str, Any], files: list[tuple[str, date]]) -> None:
    serving = {"csv": ""}

    def handler(request: httpx.Request) -> httpx.Response:
        name = serving["csv"] if request.url.path.endswith(".csv") else "publication.html"
        return httpx.Response(200, content=(FIXTURES / name).read_bytes())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        for name, on in files:
            serving["csv"] = name
            async with AsyncSession(rig["owner"]) as db:
                assert await ingest(db, client, on) != "unchanged"
                await db.commit()


async def test_two_files_on_one_date_make_one_daily_bulletin(rig: dict[str, Any]) -> None:
    # 10th: Example Care Ltd, Stable, Gone. 11th morning: Ltd->Limited rename, New added, Gone
    # removed, Stable B + GBM. 11th afternoon: New removed again, Gone back, Late added, Stable A.
    await _ingest(
        rig,
        [
            ("first.csv", date(2026, 11, 10)),
            ("second.csv", date(2026, 11, 11)),
            ("third.csv", date(2026, 11, 11)),
        ],
    )
    public = anonymous(rig)
    bulletins = (await public.get(f"{API}/changes")).json()["bulletins"]
    assert [b["date"] for b in bulletins] == ["2026-11-11", "2026-11-10"]
    listed = bulletins[0]
    assert (listed["added"], listed["removed"], listed["returned"]) == (2, 1, 0)
    day = (await public.get(f"{API}/changes/2026-11-11")).json()
    for key in ("added", "removed", "returned", "net"):
        assert day[key] == listed[key]
    assert [s["name"] for s in day["added_list"]] == ["Example Care Limited", "Late Ltd"]
    assert [s["name"] for s in day["removed_list"]] == ["Example Care Ltd"]
    assert day["returned_list"] == []
    assert day["median_added_last_28"] == 3.0
    assert len(day["possibly_same"]) == 1

    async with rig["owner"].connect() as connection:
        stable_id = await connection.scalar(
            text("select stable_id from register_sponsors where organisation_name = 'Stable Ltd'")
        )
    profile = (await public.get(f"{API}/sponsors/{stable_id}")).json()
    assert profile["entries"] == [{"type_rating": "Worker (A rating)", "route": "Skilled Worker"}]
    # The afternoon's changes come first, before the morning's.
    assert {c["change"] for c in profile["changes"][:2]} == {"rating_changed", "route_removed"}
    rating = next(c for c in profile["changes"] if c["change"] == "rating_changed")
    assert rating["detail"]["after"] == ["Worker (A rating)"]

    # A sponsor listed before the day, gone, and listed again counts as returned. The median
    # is over daily bulletins (3 and 2), not the three files (3, 2 and 1).
    await _ingest(rig, [("fourth.csv", date(2026, 11, 12))])
    later = (await public.get(f"{API}/changes/2026-11-12")).json()
    assert (later["added"], later["removed"], later["returned"]) == (0, 0, 1)
    assert [s["name"] for s in later["returned_list"]] == ["Example Care Ltd"]
    assert later["median_added_last_28"] == 2.5
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


async def test_internal_reads_have_a_separate_budget(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        rig["app"].state,
        "settings",
        rig["app"].state.settings.model_copy(update={"trusted_proxy_cidrs": "192.0.2.0/24"}),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=rig["app"], client=("192.0.2.1", 12345)),
        base_url="http://test",
    ) as public:
        for _ in range(121):
            response = await public.get(f"{API}/sitemap")
            assert response.status_code == 200, response.text


async def test_trusted_peer_with_visitor_header_keeps_per_visitor_budget(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        rig["app"].state,
        "settings",
        rig["app"].state.settings.model_copy(update={"trusted_proxy_cidrs": "192.0.2.0/24"}),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=rig["app"], client=("192.0.2.1", 12345)),
        base_url="http://test",
    ) as public:
        headers = {"X-Real-IP": "198.51.100.1"}
        for _ in range(120):
            response = await public.get(f"{API}/sitemap", headers=headers)
            assert response.status_code == 200, response.text
        assert (await public.get(f"{API}/sitemap", headers=headers)).status_code == 429
        assert (
            await public.get(f"{API}/sitemap", headers={"X-Real-IP": "198.51.100.2"})
        ).status_code == 200
        assert (await public.get(f"{API}/sitemap")).status_code == 200


async def test_untrusted_peer_keeps_connection_budget(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        rig["app"].state,
        "settings",
        rig["app"].state.settings.model_copy(update={"trusted_proxy_cidrs": "192.0.2.0/24"}),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=rig["app"], client=("198.51.100.1", 12345)),
        base_url="http://test",
    ) as public:
        for _ in range(120):
            response = await public.get(f"{API}/sitemap")
            assert response.status_code == 200, response.text
        assert (await public.get(f"{API}/sitemap")).status_code == 429
        assert (
            await public.get(f"{API}/sitemap", headers={"X-Real-IP": "198.51.100.2"})
        ).status_code == 429


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


# Shaped like the ONS Index of Place Names: Bristol is in the file before any sponsor is there.
ONS_PLACES = (
    "place22cd,place22nm,descnm,ctyhistnm,ctyltnm,cty22nm,rgn22cd,ctry22cd,lat,long\n"
    "IPN1,London,LOC,Middlesex,Greater London,Greater London,E12000007,E92000001,51.5,-0.12\n"
    "IPN2,Leeds,BUA,Yorkshire,West Yorkshire,West Yorkshire,E12000003,E92000001,53.8,-1.55\n"
    "IPN3,Bath,BUA,Somerset,Somerset,Somerset,E12000009,E92000001,51.38,-2.36\n"
    "IPN4,Bristol,BUA,Gloucestershire,Bristol,Bristol,E12000009,E92000001,51.45,-2.59\n"
)


async def test_production_import_geocodes_from_the_loaded_ons_dataset(
    rig: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    serving = {"csv": "first.csv"}

    def handler(request: httpx.Request) -> httpx.Response:
        name = serving["csv"] if request.url.path.endswith(".csv") else "publication.html"
        return httpx.Response(200, content=(FIXTURES / name).read_bytes())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        ctx = {
            "owner_engine": rig["owner"],
            "http": client,
            "now": datetime(2026, 11, 10, 10, tzinfo=UTC),
        }
        # No dataset yet: the import still succeeds and leaves everyone unplaced.
        assert await register_ingest_manual(ctx) == "imported"
        public = anonymous(rig)
        explore = (await public.get(f"{API}/explore")).json()["results"]
        assert {s["precision"] for s in explore} == {"none"}

        saved = tmp_path / "IPN_GB_2022.csv"
        saved.write_text(ONS_PLACES)
        owner_url = rig["owner"].url.render_as_string(hide_password=False)
        monkeypatch.setattr(
            cli,
            "get_settings",
            lambda: SimpleNamespace(database_url_owner=SecretStr(owner_url)),
        )
        # The operator command itself, in a thread because it runs its own event loop.
        assert (
            await asyncio.to_thread(cli.main, ["load-places", str(saved), "--version", "IPN 2022"])
            == 0
        )
        by_name = {s["name"]: s for s in (await public.get(f"{API}/explore")).json()["results"]}
        assert (by_name["Stable Ltd"]["region"], by_name["Stable Ltd"]["precision"]) == (
            "Yorkshire and The Humber",
            "exact",
        )
        assert (by_name["Gone Ltd"]["region"], by_name["Gone Ltd"]["precision"]) == (
            "South West",
            "town",
        )

        # A later production import places the new Bristol sponsor from the retained dataset.
        serving["csv"] = "second.csv"
        ctx["now"] = datetime(2026, 11, 11, 10, tzinfo=UTC)
        assert await register_ingest_manual(ctx) == "imported"
        by_name = {s["name"]: s for s in (await public.get(f"{API}/explore")).json()["results"]}
        assert (by_name["New Ltd"]["region"], by_name["New Ltd"]["precision"]) == (
            "South West",
            "town",
        )
        regions = {
            r["region"]: r["sponsors"]
            for r in (await public.get(f"{API}/regions")).json()["regions"]
        }
        assert regions["South West"] == 1  # Gone Ltd is no longer current
        assert regions["London"] == 1
        assert regions["Yorkshire and The Humber"] == 1
        await public.aclose()


async def test_production_bulk_companies_flag_matches_facets_and_refresh(
    rig: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved = tmp_path / "BasicCompanyData-2026-11.csv"
    saved.write_text(
        "CompanyName, CompanyNumber,RegAddress.PostTown,SICCode.SicText_1\n"
        "Example Care Ltd,01234567,London,87100 - Residential nursing\n"
        "Stable Ltd,00000001,Leeds,62012 - Software\n"
        " STABLE LTD.,00000002,Leeds,62012 - Software\n"
        "New Ltd,SC000003,Bristol,62012 - Software\n"
    )
    owner_url = rig["owner"].url.render_as_string(hide_password=False)
    settings = SimpleNamespace(
        database_url_owner=SecretStr(owner_url), register_bulk_match_enabled=False
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    # Load with matching disabled: retain the edition, without enriching sponsors.
    assert (
        await asyncio.to_thread(cli.main, ["load-companies", str(saved), "--version", "2026-11"])
        == 0
    )
    serving = {"csv": "first.csv"}

    def handler(request: httpx.Request) -> httpx.Response:
        name = serving["csv"] if request.url.path.endswith(".csv") else "publication.html"
        return httpx.Response(200, content=(FIXTURES / name).read_bytes())

    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client,
        anonymous(rig) as public,
    ):
        ctx = {
            "owner_engine": rig["owner"],
            "http": client,
            "settings": settings,
            "now": datetime(2026, 11, 10, 10, tzinfo=UTC),
        }
        assert await register_ingest_manual(ctx) == "imported"
        # Disabled loading also leaves existing sponsors unchanged.
        assert (
            await asyncio.to_thread(
                cli.main, ["load-companies", str(saved), "--version", "2026-11-disabled"]
            )
            == 0
        )
        async with AsyncSession(rig["owner"]) as db:
            sponsors = (await db.scalars(select(Sponsor))).all()
            assert all(s.companies_house_number is None for s in sponsors)
            assert all(s.sic_section is None for s in sponsors)
        assert (await public.get(f"{API}/explore")).json()["facets"]["industry"] == []

        # Enabling the operator command applies the retained exact-name service immediately.
        settings.register_bulk_match_enabled = True
        assert (
            await asyncio.to_thread(
                cli.main, ["load-companies", str(saved), "--version", "2026-11-enabled"]
            )
            == 0
        )
        async with AsyncSession(rig["owner"]) as db:
            care = await db.scalar(
                select(Sponsor).where(Sponsor.normalised_name == "example care ltd")
            )
            assert care is not None
            assert (care.companies_house_number, care.sic_section) == ("01234567", "Q")
            match = await db.get(CompanyMatch, care.id)
            assert match is not None
            dataset = await db.get(CompanyDataset, match.dataset_id)
            assert dataset is not None
            assert (dataset.version, dataset.source) == ("2026-11-enabled", saved.name)
            assert dataset.sha256 == hashlib.sha256(saved.read_bytes()).hexdigest()
            stable = await db.scalar(select(Sponsor).where(Sponsor.normalised_name == "stable ltd"))
            assert stable is not None
            assert stable.companies_house_number is None
        filtered = (await public.get(f"{API}/explore", params={"industry": "Q"})).json()
        assert filtered["total"] == 1
        assert filtered["results"][0]["name"] == "Example Care Ltd"
        assert filtered["sections"]["industries"] == [{"label": "Q", "count": 1}]

        # The next real import picks up a new sponsor from the active local bulk file.
        serving["csv"] = "second.csv"
        ctx["now"] = datetime(2026, 11, 11, 10, tzinfo=UTC)
        assert await register_ingest_manual(ctx) == "imported"
        filtered = (await public.get(f"{API}/explore", params={"industry": "J"})).json()
        assert filtered["total"] == 1
        assert filtered["results"][0]["name"] == "New Ltd"
        assert filtered["sections"]["industries"] == [{"label": "J", "count": 1}]
        async with AsyncSession(rig["owner"]) as db:
            new = await db.scalar(select(Sponsor).where(Sponsor.normalised_name == "new ltd"))
            assert new is not None
            assert new.companies_house_number == "SC000003"
            assert await db.get(CompanyMatch, new.id) is not None

        # A monthly refresh must remove an earlier match if the name becomes ambiguous.
        saved.write_text(
            "CompanyName,CompanyNumber,SICCode.SicText_1\n"
            "New Ltd,SC000003,62012\nNew Ltd.,00000004,62012\n"
            "Stable Ltd,00000001,87100\n"
        )
        assert (
            await asyncio.to_thread(
                cli.main, ["load-companies", str(saved), "--version", "2026-12"]
            )
            == 0
        )
        async with AsyncSession(rig["owner"]) as db:
            new = await db.scalar(select(Sponsor).where(Sponsor.normalised_name == "new ltd"))
            assert new is not None
            assert (new.companies_house_number, new.sic_section) == (None, None)
            assert await db.get(CompanyMatch, new.id) is None
        refreshed = (await public.get(f"{API}/explore", params={"industry": "Q"})).json()
        assert refreshed["total"] == 1
        assert refreshed["results"][0]["name"] == "Stable Ltd"
