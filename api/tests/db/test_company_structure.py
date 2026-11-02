"""T4.2: locations (with the postcode lookup), departments and designations: who may change them,
what is refused, that another company never sees them, and that every change is audited."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from app.core.crypto import KeyRing, set_keyring
from app.integrations.postcodes import Postcodes, normalise_postcode
from app.main import create_app
from app.modules.auth.sessions import SessionStore
from tests.db.api_support import sign_in_as, two_companies
from tests.db.support import DatabaseUnderTest, engine_for
from tests.support import TEST_REDIS_URL, build_settings


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
    app = create_app(build_settings(database_url=database.app_url, redis_url=TEST_REDIS_URL))
    sessions = SessionStore(redis)
    clients: list[httpx.AsyncClient] = []

    async def person(role: str, company: uuid.UUID) -> httpx.AsyncClient:
        client = await sign_in_as(database, sessions, app, role, company)
        clients.append(client)
        return client

    async with LifespanManager(app):
        yield {"app": app, "person": person, "a": a, "b": b, "db": database}
    for client in clients:
        await client.aclose()
    await redis.flushdb()
    await redis.aclose()


HOME = {
    "name": "Head office",
    "postcode": "sw1a 1aa",
    "address_line1": "1 Quay Street",
    "city": "London",
}


async def _actions(database: DatabaseUnderTest, company: uuid.UUID) -> list[str]:
    owner = engine_for(database.owner_url, poolclass=NullPool)
    try:
        async with owner.connect() as c:
            result = await c.execute(
                text("select action from audit_events where company_id = :c order by created_at"),
                {"c": company},
            )
            return [row[0] for row in result]
    finally:
        await owner.dispose()


def test_postcodes_are_tidied_or_refused() -> None:
    assert normalise_postcode("sw1a1aa") == "SW1A 1AA"
    assert normalise_postcode(" m1 1ae ") == "M1 1AE"
    assert normalise_postcode("EC1A 1BB") == "EC1A 1BB"
    assert normalise_postcode("not a postcode") is None
    assert normalise_postcode("12345") is None


async def test_the_first_location_is_the_default_and_there_is_only_ever_one(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    first = (await admin.post("/api/v1/locations", json=HOME)).json()
    assert first["is_default"] is True
    assert first["postcode"] == "SW1A 1AA"
    second = (
        await admin.post("/api/v1/locations", json={**HOME, "name": "Depot", "is_default": True})
    ).json()
    assert second["is_default"] is True
    listed = (await admin.get("/api/v1/locations")).json()
    assert [(item["name"], item["is_default"]) for item in listed] == [
        ("Depot", True),
        ("Head office", False),
    ]
    # The default cannot be un-set or archived while others exist; make another the default first.
    assert (
        await admin.patch(f"/api/v1/locations/{second['id']}", json={"is_default": False})
    ).status_code == 409
    assert (await admin.delete(f"/api/v1/locations/{second['id']}")).status_code == 409
    await admin.patch(f"/api/v1/locations/{first['id']}", json={"is_default": True})
    assert (await admin.delete(f"/api/v1/locations/{second['id']}")).status_code == 204
    assert [i["name"] for i in (await admin.get("/api/v1/locations")).json()] == ["Head office"]
    assert (await admin.get("/api/v1/company")).json()["locations"] == 1


async def test_a_location_must_be_a_real_address_and_nothing_extra_slips_in(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    bad = await admin.post("/api/v1/locations", json={**HOME, "postcode": "nowhere"})
    assert bad.status_code == 422
    assert bad.json()["error"]["field"] == "postcode"
    assert (
        await admin.post("/api/v1/locations", json={**HOME, "company_id": str(rig["b"])})
    ).status_code == 422
    assert (await admin.post("/api/v1/locations", json={**HOME, "name": ""})).status_code == 422


async def test_the_postcode_lookup_suggests_the_town_and_says_when_it_cannot(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])

    def reply(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("ZZ99ZZ"):
            return httpx.Response(404)
        if request.url.path.endswith("EC1A1BB"):
            return httpx.Response(500)
        return httpx.Response(
            200,
            json={
                "status": 200,
                "result": {
                    "admin_district": "Westminster",
                    "admin_county": None,
                    "country": "England",
                },
            },
        )

    rig["app"].state.postcodes = Postcodes(httpx.AsyncClient(transport=httpx.MockTransport(reply)))
    found = (await admin.get("/api/v1/locations/lookup/sw1a1aa")).json()
    assert found == {
        "postcode": "SW1A 1AA",
        "city": "Westminster",
        "county": None,
        "country": "England",
    }
    assert (await admin.get("/api/v1/locations/lookup/ZZ99ZZ")).status_code == 404
    assert (await admin.get("/api/v1/locations/lookup/EC1A1BB")).status_code == 503
    assert (await admin.get("/api/v1/locations/lookup/nonsense")).status_code == 422


async def test_departments_and_job_titles_belong_together_and_are_archived_not_deleted(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    care = (await admin.post("/api/v1/departments", json={"name": "Care"})).json()
    assert (await admin.post("/api/v1/departments", json={"name": " care "})).status_code == 409
    title = await admin.post(
        "/api/v1/designations",
        json={"title": "Senior care worker", "department_id": care["id"], "soc_code": "6135"},
    )
    assert title.status_code == 201, title.text
    assert title.json()["department_name"] == "Care"
    assert (
        await admin.post(
            "/api/v1/designations",
            json={"title": "SENIOR CARE WORKER", "department_id": care["id"]},
        )
    ).status_code == 409
    assert (
        await admin.post(
            "/api/v1/designations",
            json={"title": "Cook", "department_id": care["id"], "soc_code": "12"},
        )
    ).status_code == 422
    assert (
        await admin.post(
            "/api/v1/designations", json={"title": "Cook", "department_id": str(uuid.uuid4())}
        )
    ).status_code == 404

    assert (await admin.get("/api/v1/departments")).json()[0]["designations"] == 1
    # A department with job titles cannot be archived until they are archived or moved.
    assert (await admin.delete(f"/api/v1/departments/{care['id']}")).status_code == 409
    moved = (await admin.post("/api/v1/departments", json={"name": "Kitchen"})).json()
    patched = await admin.patch(
        f"/api/v1/designations/{title.json()['id']}",
        json={"department_id": moved["id"], "soc_code": None},
    )
    assert patched.json()["department_name"] == "Kitchen"
    assert patched.json()["soc_code"] is None
    assert (await admin.delete(f"/api/v1/departments/{care['id']}")).status_code == 204
    assert (await admin.delete(f"/api/v1/designations/{title.json()['id']}")).status_code == 204
    assert (await admin.get("/api/v1/designations")).json() == []
    # A name that was archived can be used again.
    assert (await admin.post("/api/v1/departments", json={"name": "Care"})).status_code == 201

    overview = (await admin.get("/api/v1/company")).json()
    assert (overview["departments"], overview["designations"]) == (2, 0)


async def test_who_may_change_what_and_nobody_sees_another_companys_records(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    mine = (await admin.post("/api/v1/locations", json=HOME)).json()
    dept = (await admin.post("/api/v1/departments", json={"name": "Care"})).json()
    title = (
        await admin.post(
            "/api/v1/designations", json={"title": "Carer", "department_id": dept["id"]}
        )
    ).json()

    # An HR Admin can maintain them; a People Manager can read locations and departments, not change.
    hr = await rig["person"]("hr_admin", rig["a"])
    assert (await hr.post("/api/v1/departments", json={"name": "Finance"})).status_code == 201
    staff = await rig["person"]("people_manager", rig["a"])
    assert (await staff.get("/api/v1/locations")).status_code == 200
    assert (await staff.get("/api/v1/departments")).status_code == 200
    for method, url, body in (
        ("post", "/api/v1/locations", HOME),
        ("post", "/api/v1/departments", {"name": "Nope"}),
        ("post", "/api/v1/designations", {"title": "Nope", "department_id": dept["id"]}),
        ("patch", f"/api/v1/locations/{mine['id']}", {"name": "Nope"}),
        ("delete", f"/api/v1/departments/{dept['id']}", None),
    ):
        sent = await getattr(staff, method)(url, **({"json": body} if body else {}))
        assert sent.status_code == 403, (method, url)

    # Another company sees none of it, and cannot reach it by id.
    other = await rig["person"]("company_admin", rig["b"])
    assert (await other.get("/api/v1/locations")).json() == []
    assert (await other.get("/api/v1/departments")).json() == []
    assert (
        await other.patch(f"/api/v1/locations/{mine['id']}", json={"name": "x"})
    ).status_code == 404
    assert (await other.delete(f"/api/v1/departments/{dept['id']}")).status_code == 404
    assert (
        await other.patch(f"/api/v1/designations/{title['id']}", json={"title": "x"})
    ).status_code == 404
    # Nor a department of another company for a job title.
    assert (
        await other.post("/api/v1/designations", json={"title": "Spy", "department_id": dept["id"]})
    ).status_code == 404

    assert await _actions(rig["db"], rig["a"]) == [
        "location.created",
        "department.created",
        "designation.created",
        "department.created",
    ]
