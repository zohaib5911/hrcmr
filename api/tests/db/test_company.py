"""T4.1: the company's details, the lists, the logo, and the Companies House lookup."""

from __future__ import annotations

import os
import struct
import zlib
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from app.core.crypto import KeyRing, set_keyring
from app.integrations.companies_house import CompaniesHouse
from app.main import create_app
from app.modules.auth.sessions import SessionStore
from app.modules.companies.reference import LEGAL_STRUCTURES, SECTORS, TRADING_PERIODS
from tests.db.api_support import sign_in_as, two_companies
from tests.db.support import DatabaseUnderTest, engine_for
from tests.support import TEST_REDIS_URL, build_settings

S3 = os.environ.get("TEST_S3_ENDPOINT", "http://localhost:9000")
S3_USER = os.environ.get("RUSTFS_ACCESS_KEY", "rustfsadmin")
S3_PASSWORD = os.environ.get("RUSTFS_SECRET_KEY", "rustfsadmin")


@pytest.fixture(autouse=True)
def _keys() -> Any:
    set_keyring(KeyRing(keys={"k1": os.urandom(32)}, active_kid="k1", blind_key=os.urandom(32)))
    yield
    set_keyring(None)


def png() -> bytes:
    """A real 1x1 PNG."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
        + chunk(b"IEND", b"")
    )


@pytest.fixture
async def rig(database: DatabaseUnderTest) -> AsyncIterator[dict[str, Any]]:
    redis = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    await redis.flushdb()
    a, b = await two_companies(database)
    settings = build_settings(
        database_url=database.app_url,
        redis_url=TEST_REDIS_URL,
        r2_endpoint=S3,
        r2_access_key_id=S3_USER,
        r2_secret_access_key=S3_PASSWORD,
        r2_bucket_files="files-dev",
    )
    app = create_app(settings)
    sessions = SessionStore(redis)
    clients: list[httpx.AsyncClient] = []

    async def person(role: str, company: Any) -> httpx.AsyncClient:
        client = await sign_in_as(database, sessions, app, role, company)
        clients.append(client)
        return client

    async with LifespanManager(app):
        yield {"app": app, "person": person, "a": a, "b": b, "db": database}
    for client in clients:
        await client.aclose()
    await redis.flushdb()
    await redis.aclose()


async def _events(database: DatabaseUnderTest, company: Any, prefix: str) -> list[Any]:
    owner = engine_for(database.owner_url, poolclass=NullPool)
    try:
        async with owner.connect() as c:
            result = await c.execute(
                text(
                    "select action, before, after from audit_events "
                    "where company_id = :c and action like :p order by created_at"
                ),
                {"c": company, "p": f"{prefix}%"},
            )
            return list(result.mappings())
    finally:
        await owner.dispose()


async def test_the_overview_is_this_companys_own_and_says_what_the_server_can_do(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    other = await rig["person"]("company_admin", rig["b"])
    seen = (await admin.get("/api/v1/company")).json()
    assert seen["company"]["id"] == str(rig["a"])
    assert seen["company"]["name"] == "Company a"
    assert seen["company"]["plan"] == "annual"  # the test companies are on a paid plan
    assert seen["users"] == 1
    assert seen["features"] == {"companies_house_lookup": False, "ai": False}
    assert (await other.get("/api/v1/company")).json()["company"]["id"] == str(rig["b"])


async def test_details_change_only_for_those_who_may_and_every_change_is_recorded(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    changed = await admin.patch(
        "/api/v1/company",
        json={
            "name": "  Harbourside Care Ltd ",
            "trading_name": "Harbourside",
            "registered_number": "1234567",
            "type_of_organisation": "private_limited_by_shares",
            "trading_period": "over_36_months",
            "sector": "Q",
            "contact_email": "hello@example.com",
            "contact_phone": "+44 20 7946 0000",
            "website": "https://example.com",
            "bank_holiday_region": "scotland",
            "timezone": "Europe/London",
            "changed_name_last_5_years": True,
            "previous_company_name": "Harbour Care",
        },
    )
    assert changed.status_code == 200, changed.text
    body = changed.json()
    assert body["name"] == "Harbourside Care Ltd"
    assert body["registered_number"] == "01234567"
    assert body["previous_company_name"] == "Harbour Care"

    (event,) = await _events(rig["db"], rig["a"], "company.updated")
    assert event["before"]["name"] == "Company a"
    assert event["after"]["name"] == "Harbourside Care Ltd"

    # A "no" clears what only a "yes" needs; sending nothing new records nothing.
    cleared = await admin.patch("/api/v1/company", json={"changed_name_last_5_years": False})
    assert cleared.json()["previous_company_name"] is None
    await admin.patch("/api/v1/company", json={"changed_name_last_5_years": False})
    assert len(await _events(rig["db"], rig["a"], "company.updated")) == 2

    # An HR Admin and an employee can read the company but not change it.
    for role in ("hr_admin", "employee"):
        person = await rig["person"](role, rig["a"])
        assert (await person.get("/api/v1/company")).status_code == 200
        assert (await person.patch("/api/v1/company", json={"name": "Nope"})).status_code == 403
    # And nobody changes another company's details.
    other = await rig["person"]("company_admin", rig["b"])
    await other.patch("/api/v1/company", json={"name": "Company b renamed"})
    assert (await admin.get("/api/v1/company")).json()["company"]["name"] == "Harbourside Care Ltd"


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"name": ""}, "name"),
        ({"timezone": "Mars/Olympus"}, "timezone"),
        ({"registered_number": "12-34"}, "registered_number"),
        ({"website": "example.com"}, "website"),
        ({"contact_phone": "call me"}, "contact_phone"),
        ({"sector": "Z"}, "sector"),
        ({"changed_name_last_5_years": True, "previous_company_name": ""}, None),
    ],
)
async def test_nonsense_is_refused_with_the_field_it_is_about(
    rig: dict[str, Any], payload: dict[str, Any], field: str | None
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    refused = await admin.patch("/api/v1/company", json=payload)
    assert refused.status_code == 422
    if field:
        assert refused.json()["error"]["field"] == field


async def test_the_lists_match_the_plan(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    options = (await admin.get("/api/v1/company/options")).json()
    assert len(options["legal_structures"]) == len(LEGAL_STRUCTURES) == 12
    assert len(options["trading_periods"]) == len(TRADING_PERIODS) == 5
    assert len(options["sectors"]) == len(SECTORS) == 21
    assert [o["value"] for o in options["bank_holiday_regions"]] == [
        "england-and-wales",
        "scotland",
        "northern-ireland",
    ]
    assert "Europe/London" in options["timezones"]


async def test_a_logo_is_stored_scanned_shown_and_removed(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    assert (await admin.get("/api/v1/company/logo")).status_code == 404

    sent = await admin.post(
        "/api/v1/company/logo", files={"file": ("logo.png", png(), "image/png")}
    )
    assert sent.status_code == 204, sent.text
    assert (await admin.get("/api/v1/company")).json()["company"]["has_logo"] is True
    shown = await admin.get("/api/v1/company/logo")
    assert shown.status_code == 200
    assert shown.headers["content-type"] == "image/png"
    assert shown.content == png()
    # Everyone in the company sees it; another company does not.
    staff = await rig["person"]("employee", rig["a"])
    assert (await staff.get("/api/v1/company/logo")).status_code == 200
    other = await rig["person"]("company_admin", rig["b"])
    assert (await other.get("/api/v1/company/logo")).status_code == 404

    # Only pictures, and only small ones.
    pdf = b"%PDF-1.4\n%%EOF\n"
    refused = await admin.post(
        "/api/v1/company/logo", files={"file": ("logo.pdf", pdf, "application/pdf")}
    )
    assert refused.status_code == 415
    big = await admin.post(
        "/api/v1/company/logo",
        files={"file": ("big.png", png() + b"\0" * (2 * 1024 * 1024), "image/png")},
    )
    assert big.status_code == 413

    assert (await admin.delete("/api/v1/company/logo")).status_code == 204
    assert (await admin.get("/api/v1/company/logo")).status_code == 404
    actions = [e["action"] for e in await _events(rig["db"], rig["a"], "company.logo")]
    assert actions == ["company.logo_changed", "company.logo_removed"]


async def test_the_companies_house_lookup_fills_in_what_it_finds(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    # Switched off until the server has a key.
    assert (await admin.get("/api/v1/company/companies-house/01234567")).status_code == 404

    def reply(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/company/01234567") or request.url.path.endswith(
            "/00000000"
        )
        if request.url.path.endswith("/00000000"):
            return httpx.Response(404)
        return httpx.Response(
            200,
            json={
                "company_name": "HARBOURSIDE CARE LTD",
                "company_status": "active",
                "type": "ltd",
                "registered_office_address": {
                    "address_line_1": "1 Quay Street",
                    "locality": "Hull",
                    "postal_code": "HU1 1AA",
                    "country": "England",
                },
            },
        )

    rig["app"].state.companies_house = CompaniesHouse(
        "a-test-key", client=httpx.AsyncClient(transport=httpx.MockTransport(reply))
    )
    assert (await admin.get("/api/v1/company")).json()["features"]["companies_house_lookup"] is True
    found = (await admin.get("/api/v1/company/companies-house/1234567")).json()
    assert found["name"] == "HARBOURSIDE CARE LTD"
    assert found["legal_structure"] == "private_limited_by_shares"
    assert found["address"]["postcode"] == "HU1 1AA"
    assert (await admin.get("/api/v1/company/companies-house/00000000")).status_code == 404
    assert (await admin.get("/api/v1/company/companies-house/not-a-number")).status_code == 422
