"""T6.1: the employee list and summary: filters, search, what each role can reach, other
companies, and what is left out."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from app.core.crypto import KeyRing, set_keyring
from app.main import create_app
from app.modules.auth.sessions import SessionStore
from tests.db.api_support import sign_in_as, two_companies
from tests.db.support import DatabaseUnderTest, engine_for
from tests.support import TEST_REDIS_URL, build_settings

API = "/api/v1"


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
        yield {"person": person, "a": a, "b": b, "owner": owner}
    for client in clients:
        await client.aclose()
    await owner.dispose()
    await redis.flushdb()
    await redis.aclose()


async def _employee(
    rig: dict[str, Any],
    company: uuid.UUID,
    number: str,
    first: str,
    last: str,
    *,
    status: str = "active",
    department: uuid.UUID | None = None,
    manager: uuid.UUID | None = None,
) -> uuid.UUID:
    ident = uuid.uuid4()
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "insert into employees (id, company_id, employee_number, first_name, last_name, "
                "email, hire_date, status) values (:i, :c, :n, :f, :l, :e, '2025-01-06', :s)"
            ),
            {
                "i": ident,
                "c": company,
                "n": number,
                "f": first,
                "l": last,
                "e": f"{first}@example.com".lower(),
                "s": status,
            },
        )
        await c.execute(
            text(
                "insert into employee_assignments (employee_id, company_id, department_id, "
                "reporting_authority_employee_id, employment_type, effective_from) "
                "values (:i, :c, :d, :m, 'full_time', '2025-01-06')"
            ),
            {"i": ident, "c": company, "d": department, "m": manager},
        )
    return ident


async def _department(rig: dict[str, Any], company: uuid.UUID, name: str) -> uuid.UUID:
    ident = uuid.uuid4()
    async with rig["owner"].begin() as c:
        await c.execute(
            text("insert into departments (id, company_id, name) values (:i, :c, :n)"),
            {"i": ident, "c": company, "n": name},
        )
    return ident


def _names(listing: dict[str, Any]) -> list[str]:
    return [e["first_name"] for e in listing["employees"]]


async def test_the_list_filters_searches_and_summarises(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    care = await _department(rig, rig["a"], "Care")
    await _employee(rig, rig["a"], "E 001", "Amira", "Hassan", department=care)
    await _employee(rig, rig["a"], "E002", "Ben", "Okafor", status="on_leave")
    await _employee(rig, rig["a"], "E003", "Cleo", "Ng", status="leaver")
    await _employee(rig, rig["a"], "E004", "Dev", "Patel", status="archived")
    await _employee(rig, rig["b"], "E001", "Zed", "Other")  # another company, same number

    def get(**params: Any) -> Any:
        return admin.get(f"{API}/employees", params=params)

    everyone = (await get()).json()
    assert [e["last_name"] for e in everyone["employees"]] == ["Hassan", "Ng", "Okafor"]
    assert everyone["total"] == 3  # archived records are left out unless asked for
    first = everyone["employees"][0]
    assert (first["employee_number"], first["department"], first["status"]) == (
        "E 001",
        "Care",
        "active",
    )
    assert "ni_number" not in str(everyone)

    assert _names((await get(status="leaver")).json()) == ["Cleo"]
    assert len((await get(archived="true")).json()["employees"]) == 4
    assert _names((await get(status="archived")).json()) == ["Dev"]
    assert _names((await get(department_id=str(care))).json()) == ["Amira"]
    assert _names((await get(q="e001")).json()) == ["Amira"]  # a number, ignoring case and spaces
    assert _names((await get(q="ben okafor")).json()) == ["Ben"]
    assert (await get(q="%")).json()["employees"] == []
    assert (await get(status="gone")).status_code == 422

    assert (await admin.get(f"{API}/employees/summary")).json() == {
        "total": 3,
        "active": 1,
        "on_leave": 1,
        "leavers": 1,
        "archived": 1,
        "rtw_needs_attention": 3,
        "rtw_verified": 0,
    }


async def test_each_role_sees_only_what_its_permission_reaches(rig: dict[str, Any]) -> None:
    boss = await _employee(rig, rig["a"], "M1", "Mona", "Boss")
    mine = await _employee(rig, rig["a"], "M2", "Rae", "Report", manager=boss)
    await _employee(rig, rig["a"], "M3", "Sam", "Stranger")
    manager = await rig["person"]("people_manager", rig["a"])
    employee = await rig["person"]("employee", rig["a"])
    async with rig["owner"].begin() as c:
        link = "update memberships set employee_id = :e where role = :r and company_id = :c"
        await c.execute(text(link), {"e": boss, "r": "people_manager", "c": rig["a"]})
        await c.execute(text(link), {"e": mine, "r": "employee", "c": rig["a"]})
    hr = await rig["person"]("hr_admin", rig["a"])

    assert len((await hr.get(f"{API}/employees")).json()["employees"]) == 3
    seen = [e["last_name"] for e in (await manager.get(f"{API}/employees")).json()["employees"]]
    assert seen == ["Boss", "Report"]  # themselves and their report, not the stranger
    own = [e["last_name"] for e in (await employee.get(f"{API}/employees")).json()["employees"]]
    assert own == ["Report"]
    assert (await manager.get(f"{API}/employees/summary")).json()["total"] == 2
    recruiter = await rig["person"]("recruiter", rig["a"])
    assert (await recruiter.get(f"{API}/employees")).status_code == 403


NEW = {
    "first_name": "Amira",
    "last_name": "Hassan",
    "email": "Amira@Example.com",
    "phone": "07700 900123",
    "employee_number": "E 001",
    "hire_date": "2025-01-06",
}


async def test_creating_an_employee_checks_the_number_the_date_and_who_may(
    rig: dict[str, Any],
) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    made = await hr.post(f"{API}/employees", json=NEW)
    assert made.status_code == 201, made.text
    assert (made.json()["email"], made.json()["status"]) == ("amira@example.com", "active")

    # The number is unique ignoring case and spaces, but only within the company.
    for clash in ("e001", "E  001", " e 001 "):
        again = await hr.post(f"{API}/employees", json={**NEW, "employee_number": clash})
        assert again.status_code == 409, clash
        assert again.json()["error"]["field"] == "employee_number"
    other = await rig["person"]("hr_admin", rig["b"])
    assert (await other.post(f"{API}/employees", json=NEW)).status_code == 201

    soon = (datetime.now(UTC).date() + timedelta(days=300)).isoformat()
    later = (datetime.now(UTC).date() + timedelta(days=400)).isoformat()
    ok = await hr.post(f"{API}/employees", json={**NEW, "employee_number": "E2", "hire_date": soon})
    assert ok.status_code == 201
    too_far = await hr.post(
        f"{API}/employees", json={**NEW, "employee_number": "E3", "hire_date": later}
    )
    assert too_far.status_code == 422
    for bad in (
        {"first_name": "  "},
        {"email": "nope"},
        {"employee_number": ""},
        {"status": "archived"},
        {"surprise": 1},
    ):
        refused = await hr.post(f"{API}/employees", json={**NEW, "employee_number": "E9", **bad})
        assert refused.status_code == 422, bad

    manager = await rig["person"]("people_manager", rig["a"])
    assert (
        await manager.post(f"{API}/employees", json={**NEW, "employee_number": "E7"})
    ).status_code == 403
    async with rig["owner"].connect() as c:
        events = (
            await c.execute(
                text(
                    "select action, after from audit_events "
                    "where company_id = :c and action = 'employee.created'"
                ),
                {"c": rig["a"]},
            )
        ).all()
    assert len(events) == 2
    assert events[0][1]["employee_number"] in ("E 001", "E2")
    listed = (await hr.get(f"{API}/employees")).json()
    assert [e["employee_number"] for e in listed["employees"]] == ["E 001", "E2"]
