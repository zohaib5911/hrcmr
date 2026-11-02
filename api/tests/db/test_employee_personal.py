"""T6.4: the Personal tab: details, address, emergency contacts, and the masked identity and bank
details that only show in full after a step-up check, with every reveal audited."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from app.core.crypto import KeyRing, set_keyring
from app.integrations.postcodes import Postcodes
from app.main import create_app
from app.modules.auth.sessions import SessionStore
from tests.db.api_support import sign_in_as, two_companies
from tests.db.support import DatabaseUnderTest, engine_for
from tests.support import TEST_REDIS_URL, build_settings

API = "/api/v1"
NI = "AB 12 34 56 C"
PASSPORT = "123456789"


@pytest.fixture(autouse=True)
def _keys() -> Iterator[None]:
    set_keyring(KeyRing(keys={"k1": os.urandom(32)}, active_kid="k1", blind_key=os.urandom(32)))
    yield
    set_keyring(None)


@pytest.fixture
async def rig(database: DatabaseUnderTest) -> AsyncIterator[dict[str, Any]]:
    redis = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    await redis.flushdb()
    a, b = await two_companies(database)
    owner = engine_for(database.owner_url, poolclass=NullPool)
    app = create_app(build_settings(database_url=database.app_url, redis_url=TEST_REDIS_URL))
    sessions = SessionStore(redis)
    clients: list[httpx.AsyncClient] = []

    async def person(role: str, company: uuid.UUID) -> httpx.AsyncClient:
        client = await sign_in_as(database, sessions, app, role, company)
        clients.append(client)
        return client

    async with LifespanManager(app):
        yield {"person": person, "a": a, "b": b, "owner": owner, "app": app, "sessions": sessions}
    for client in clients:
        await client.aclose()
    await owner.dispose()
    await redis.flushdb()
    await redis.aclose()


async def _employee(rig: dict[str, Any], company: uuid.UUID, number: str) -> uuid.UUID:
    ident = uuid.uuid4()
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "insert into employees (id, company_id, employee_number, first_name, last_name, "
                "email, hire_date) values (:i, :c, :n, 'Amira', 'Hassan', 'a@example.com', "
                "'2025-01-06')"
            ),
            {"i": ident, "c": company, "n": number},
        )
    return ident


async def _step_up(admin: httpx.AsyncClient, rig: dict[str, Any]) -> None:
    token = admin.cookies.get("brand_session")
    data = await rig["sessions"].get(token)
    await rig["sessions"].mark_step_up(token, data)


DETAILS = {
    "first_name": "Amira",
    "last_name": "Hassan",
    "email": "Amira.Hassan@Example.com",
    "phone": "07700 900123",
    "alt_phone": None,
    "date_of_birth": "1990-04-02",
    "gender": "female",
    "marital_status": "married",
    "nationality": "British",
}


async def test_details_address_and_contacts_are_saved_and_audited(rig: dict[str, Any]) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    base = f"{API}/employees/{emp}"

    empty = (await hr.get(f"{base}/personal")).json()
    assert (empty["details"]["gender"], empty["address"], empty["contacts"]) == (
        "not_specified",
        None,
        [],
    )

    saved = await hr.put(f"{base}/personal", json=DETAILS)
    assert saved.status_code == 200, saved.text
    assert saved.json()["details"]["email"] == "amira.hassan@example.com"
    assert saved.json()["details"]["marital_status"] == "married"
    for bad in ({"date_of_birth": "2999-01-01"}, {"gender": "robot"}, {"email": "nope"}):
        assert (await hr.put(f"{base}/personal", json={**DETAILS, **bad})).status_code == 422, bad

    address = {"postcode": "SW1A 1AA", "line1": "1 High Street", "city_county": "London"}
    put = await hr.put(f"{base}/address", json=address)
    assert put.status_code == 200, put.text
    again = await hr.put(f"{base}/address", json={**address, "line1": "2 High Street"})
    assert again.json()["line1"] == "2 High Street"  # one current address, replaced in place
    assert (await hr.put(f"{base}/address", json={"line1": " "})).status_code == 422

    contact = {"name": "Sam Hassan", "relationship": "civil_partner", "phone": "07700 900456"}
    made = await hr.post(f"{base}/contacts", json=contact)
    assert made.status_code == 201, made.text
    cid = made.json()["id"]
    assert (
        await hr.post(f"{base}/contacts", json={**contact, "relationship": "boss"})
    ).status_code == 422
    edited = await hr.put(f"{base}/contacts/{cid}", json={**contact, "relationship": "guardian"})
    assert edited.json()["relationship"] == "guardian"
    assert (await hr.get(f"{base}/personal")).json()["contacts"][0]["name"] == "Sam Hassan"
    assert (await hr.delete(f"{base}/contacts/{cid}")).status_code == 204
    assert (await hr.delete(f"{base}/contacts/{cid}")).status_code == 404

    async with rig["owner"].connect() as c:
        actions = {
            r[0]
            for r in await c.execute(
                text("select action from audit_events where company_id = :c"), {"c": rig["a"]}
            )
        }
    assert {
        "employee.personal_details_changed",
        "employee.address_changed",
        "employee.emergency_contact_added",
        "employee.emergency_contact_changed",
        "employee.emergency_contact_removed",
    } <= actions


async def test_identity_and_bank_are_masked_until_a_step_up_and_each_reveal_is_audited(
    rig: dict[str, Any],
) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    base = f"{API}/employees/{emp}"

    ident = {"ni_number": "ab123456c", "passport_number": PASSPORT, "passport_country": "UK"}
    saved = await hr.put(f"{base}/identity", json=ident)
    assert saved.status_code == 200, saved.text
    assert saved.json()["ni_number"] == "•• •• •• 56 C"
    assert PASSPORT not in saved.text
    assert (await hr.put(f"{base}/identity", json={"ni_number": "ZZ123456A"})).status_code == 422
    bank = {
        "account_holder": "A Hassan",
        "bank_name": "Example Bank",
        "sort_code": "123456",
        "account_number": "12345678",
    }
    assert (await hr.put(f"{base}/bank", json=bank)).json()["sort_code"].endswith("56")
    for bad in ({"sort_code": "12"}, {"account_number": "1234"}):
        assert (await hr.put(f"{base}/bank", json={**bank, **bad})).status_code == 422, bad
    # A second account replaces the first, which is kept as history.
    await hr.put(f"{base}/bank", json={**bank, "bank_name": "Other Bank"})

    tab = (await hr.get(f"{base}/personal")).json()
    assert tab["sensitive_visible"] is True
    assert tab["bank"]["bank_name"] == "Other Bank"
    assert "12345678" not in str(tab)
    assert "123456C" not in str(tab)

    refused = await hr.post(f"{base}/reveal", json={"field": "identity"})
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "STEP_UP_REQUIRED"
    await _step_up(hr, rig)
    shown = await hr.post(f"{base}/reveal", json={"field": "identity"})
    assert shown.json()["identity"] == {"ni_number": NI, "passport_number": PASSPORT}
    paid = await hr.post(f"{base}/reveal", json={"field": "bank"})
    assert paid.json()["bank"] == {"sort_code": "12-34-56", "account_number": "12345678"}

    other = await _employee(rig, rig["a"], "E2")
    clash = await hr.put(f"{API}/employees/{other}/identity", json={"ni_number": NI})
    assert clash.status_code == 409
    assert clash.json()["error"]["field"] == "ni_number"

    async with rig["owner"].connect() as c:
        rows = (
            await c.execute(
                text(
                    "select action, after::text from audit_events "
                    "where company_id = :c and action like 'employee.%'"
                ),
                {"c": rig["a"]},
            )
        ).all()
        current = (
            await c.execute(text("select count(*) from employee_bank_details where is_current"))
        ).scalar_one()
        history = (await c.execute(text("select count(*) from employee_bank_details"))).scalar_one()
    assert sum(1 for r in rows if r[0] == "employee.sensitive_revealed") == 2
    assert not any(PASSPORT in r[1] or "12345678" in r[1] for r in rows if r[1])
    assert (current, history) == (1, 2)


async def test_who_may_see_and_change_what(rig: dict[str, Any]) -> None:
    mine = await _employee(rig, rig["a"], "E1")
    theirs = await _employee(rig, rig["a"], "E2")
    foreign = await _employee(rig, rig["b"], "E1")
    me = await rig["person"]("employee", rig["a"])
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "update memberships set employee_id = :e where role = 'employee' and company_id = :c"
            ),
            {"e": mine, "c": rig["a"]},
        )
    hr = await rig["person"]("hr_admin", rig["a"])
    await hr.put(f"{API}/employees/{mine}/identity", json={"ni_number": NI})

    own = await me.get(f"{API}/employees/{mine}/personal")
    assert own.status_code == 200
    assert own.json()["identity"]["ni_number"] == "•• •• •• 56 C"
    assert (await me.get(f"{API}/employees/{theirs}/personal")).status_code == 404
    assert (await me.put(f"{API}/employees/{theirs}/personal", json=DETAILS)).status_code == 404
    assert (
        await me.put(f"{API}/employees/{mine}/identity", json={"ni_number": NI})
    ).status_code == 403
    assert (await hr.get(f"{API}/employees/{foreign}/personal")).status_code == 404

    boss = await _employee(rig, rig["a"], "E9")
    manager = await rig["person"]("people_manager", rig["a"])
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "update memberships set employee_id = :e "
                "where role = 'people_manager' and company_id = :c"
            ),
            {"e": boss, "c": rig["a"]},
        )
        await c.execute(
            text(
                "insert into employee_assignments (employee_id, company_id, "
                "reporting_authority_employee_id, employment_type, effective_from) "
                "values (:e, :c, :b, 'full_time', '2025-01-06')"
            ),
            {"e": mine, "c": rig["a"], "b": boss},
        )
    seen = (await manager.get(f"{API}/employees/{mine}/personal")).json()
    assert seen["sensitive_visible"] is False
    assert seen["identity"] is None

    def reply(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": 200, "result": {"admin_district": "Westminster", "country": "England"}},
        )

    rig["app"].state.postcodes = Postcodes(httpx.AsyncClient(transport=httpx.MockTransport(reply)))
    found = await hr.get(f"{API}/employee-lookups/postcode/sw1a1aa")
    assert found.json()["city"] == "Westminster"
