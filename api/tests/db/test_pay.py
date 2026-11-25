"""T4.7: bank accounts (encrypted, shown masked), tax codes, payment types, pay bands and pay
schedules: who may use them, what is refused, other companies, and the audit trail."""

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


ACCOUNT = {
    "label": "Main current account",
    "bank_name": "Example Bank",
    "account_holder": "Harbourside Care Ltd",
    "sort_code": "12-34-56",
    "account_number": "87654321",
}


async def test_bank_accounts_are_stored_encrypted_and_only_shown_masked(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    made = await admin.post(f"{API}/bank-accounts", json=ACCOUNT)
    assert made.status_code == 201, made.text
    account = made.json()
    assert account["sort_code_masked"] == "••-••-56"
    assert account["account_number_masked"] == "••••4321"
    assert account["is_primary"] is True  # the first one is the main one
    assert "123456" not in made.text
    assert "87654321" not in made.text

    async with rig["owner"].connect() as c:
        stored = (
            await c.execute(text("select sort_code, account_number from company_bank_accounts"))
        ).one()
    assert all(v.startswith("v1:") and "123456" not in v and "87654321" not in v for v in stored)

    second = (
        await admin.post(
            f"{API}/bank-accounts",
            json={**ACCOUNT, "label": "Savings", "account_number": "11112222", "is_primary": True},
        )
    ).json()
    listed = (await admin.get(f"{API}/bank-accounts")).json()
    assert [a["label"] for a in listed] == ["Savings", "Main current account"]
    assert [a["is_primary"] for a in listed] == [True, False]

    # Changing a name keeps the numbers; sending new ones replaces them.
    kept = await admin.patch(
        f"{API}/bank-accounts/{second['id']}", json={"bank_name": "Other Bank"}
    )
    assert kept.json()["account_number_masked"] == "••••2222"
    moved = await admin.patch(
        f"{API}/bank-accounts/{second['id']}", json={"account_number": "99998888"}
    )
    assert moved.json()["account_number_masked"] == "••••8888"

    for bad in ({"sort_code": "12345"}, {"account_number": "1234"}, {"sort_code": None}):
        assert (
            await admin.patch(f"{API}/bank-accounts/{second['id']}", json=bad)
        ).status_code == 422
    dup = await admin.post(f"{API}/bank-accounts", json={**ACCOUNT, "label": "savings"})
    assert dup.status_code == 409
    assert (await admin.delete(f"{API}/bank-accounts/{second['id']}")).status_code == 409  # main
    await admin.patch(f"{API}/bank-accounts/{account['id']}", json={"is_primary": True})
    assert (await admin.delete(f"{API}/bank-accounts/{second['id']}")).status_code == 204

    async with rig["owner"].connect() as c:
        rows = (
            await c.execute(
                text(
                    "select action, before, after from audit_events where action like 'bank_account%'"
                )
            )
        ).all()
    assert rows
    assert "87654321" not in str(rows)
    assert "99998888" not in str(rows)
    assert "123456" not in str(rows)


async def test_a_new_account_number_with_the_same_last_digits_is_audited_once(
    rig: dict[str, Any],
) -> None:
    """ISS-07: the masked values look the same, but the change is still recorded, without digits."""
    admin = await rig["person"]("company_admin", rig["a"])
    made = (await admin.post(f"{API}/bank-accounts", json=ACCOUNT)).json()
    sql = (
        "select summary, before, after from audit_events "
        "where action = 'bank_account.updated' and entity_id = :i"
    )

    async def events() -> list[Any]:
        async with rig["owner"].connect() as c:
            return list((await c.execute(text(sql), {"i": made["id"]})).all())

    same = await admin.patch(f"{API}/bank-accounts/{made['id']}", json={"sort_code": "12-34-56"})
    assert same.status_code == 200, same.text
    assert await events() == []  # nothing really changed

    changed = await admin.patch(
        f"{API}/bank-accounts/{made['id']}",
        json={"account_number": "11114321", "sort_code": "65-43-56"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["account_number_masked"] == "••••4321"  # looks the same
    rows = await events()
    assert len(rows) == 1
    assert "account_number" in rows[0].summary
    assert "sort_code" in rows[0].summary
    for secret in ("11114321", "87654321", "654356", "65-43-56", "123456", "12-34-56"):
        assert secret not in str(rows)


async def test_bank_accounts_are_for_company_admins_and_private_to_the_company(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    await admin.post(f"{API}/bank-accounts", json=ACCOUNT)
    hr = await rig["person"]("hr_admin", rig["a"])
    assert (await hr.get(f"{API}/bank-accounts")).status_code == 200
    assert (await hr.post(f"{API}/bank-accounts", json=ACCOUNT)).status_code == 403
    employee = await rig["person"]("employee", rig["a"])
    assert (await employee.get(f"{API}/bank-accounts")).status_code == 403
    other = await rig["person"]("company_admin", rig["b"])
    assert (await other.get(f"{API}/bank-accounts")).json() == []


async def test_tax_codes_payment_types_and_pay_bands(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    tax = await admin.post(
        f"{API}/tax-codes",
        json={"code": "1257l", "reference": "Standard", "deduction_percentage": "20"},
    )
    assert tax.status_code == 201, tax.text
    assert tax.json()["code"] == "1257L"
    assert (
        await admin.post(f"{API}/tax-codes", json={"code": "1257L", "deduction_percentage": "0"})
    ).status_code == 409
    assert (
        await admin.post(f"{API}/tax-codes", json={"code": "BR", "deduction_percentage": "101"})
    ).status_code == 422
    changed = await admin.put(
        f"{API}/tax-codes/{tax.json()['id']}",
        json={"code": "1257L", "deduction_percentage": "19.5"},
    )
    assert changed.json()["deduction_percentage"] == "19.50"

    kind = await admin.post(
        f"{API}/payment-types", json={"name": "Hourly", "min_hourly_rate": "12.5"}
    )
    assert kind.status_code == 201
    assert (
        await admin.post(f"{API}/payment-types", json={"name": "hourly", "min_hourly_rate": "1"})
    ).status_code == 409
    assert (
        await admin.post(f"{API}/payment-types", json={"name": "X", "min_hourly_rate": "-1"})
    ).status_code == 422

    band = {"name": "Grade 3", "min_annual": "28000", "max_annual": "34000"}
    made = await admin.post(f"{API}/pay-bands", json=band)
    assert made.status_code == 201
    assert made.json()["currency"] == "GBP"
    inverted = await admin.post(
        f"{API}/pay-bands", json={**band, "name": "Backwards", "min_annual": "50000"}
    )
    assert inverted.status_code == 422
    assert (
        await admin.post(f"{API}/pay-bands", json={**band, "currency": "pounds"})
    ).status_code == 422

    # Archived records leave the list and free their name.
    assert (await admin.delete(f"{API}/pay-bands/{made.json()['id']}")).status_code == 204
    assert (await admin.get(f"{API}/pay-bands")).json() == []
    assert (await admin.post(f"{API}/pay-bands", json=band)).status_code == 201
    assert (await admin.delete(f"{API}/pay-bands/{made.json()['id']}")).status_code == 404

    hr = await rig["person"]("hr_admin", rig["a"])
    assert (await hr.post(f"{API}/pay-bands", json={**band, "name": "HR made"})).status_code == 201
    employee = await rig["person"]("employee", rig["a"])
    for path in ("tax-codes", "payment-types", "pay-bands", "pay-schedules"):
        assert (await employee.get(f"{API}/{path}")).status_code == 403
    other = await rig["person"]("company_admin", rig["b"])
    assert (await other.get(f"{API}/tax-codes")).json() == []
    assert (
        await other.put(
            f"{API}/tax-codes/{tax.json()['id']}", json={"code": "X", "deduction_percentage": "1"}
        )
    ).status_code == 404


async def test_pay_schedules_need_a_pay_day_that_fits_the_frequency(rig: dict[str, Any]) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    weekly = {
        "name": "Weekly Friday",
        "frequency": "weekly",
        "pay_day_kind": "weekday",
        "pay_day_value": 5,
    }
    made = await admin.post(f"{API}/pay-schedules", json=weekly)
    assert made.status_code == 201, made.text
    monthly = {
        "name": "Month end",
        "frequency": "monthly",
        "pay_day_kind": "last_working_day",
        "pay_day_value": 7,
    }
    assert (await admin.post(f"{API}/pay-schedules", json=monthly)).json()["pay_day_value"] is None
    assert (
        await admin.post(
            f"{API}/pay-schedules",
            json={
                "name": "The 25th",
                "frequency": "monthly",
                "pay_day_kind": "day_of_month",
                "pay_day_value": 25,
            },
        )
    ).status_code == 201

    for bad in (
        {**weekly, "name": "A", "pay_day_kind": "last_day", "pay_day_value": None},
        {**weekly, "name": "B", "pay_day_value": 8},
        {**weekly, "name": "C", "pay_day_value": None},
        {"name": "D", "frequency": "monthly", "pay_day_kind": "weekday", "pay_day_value": 1},
        {"name": "E", "frequency": "monthly", "pay_day_kind": "day_of_month", "pay_day_value": 29},
        {**weekly, "name": "F", "frequency": "yearly"},
    ):
        assert (await admin.post(f"{API}/pay-schedules", json=bad)).status_code == 422, bad
    renamed = await admin.put(
        f"{API}/pay-schedules/{made.json()['id']}", json={**weekly, "name": "Friday pay"}
    )
    assert renamed.json()["name"] == "Friday pay"

    async with rig["owner"].connect() as c:
        actions = [
            r[0]
            for r in await c.execute(
                text(
                    "select action from audit_events where action like 'pay_schedule%' order by created_at"
                )
            )
        ]
    assert actions == ["pay_schedule.created"] * 3 + ["pay_schedule.updated"]


@pytest.mark.parametrize(
    ("path", "table", "field", "body"),
    [
        ("tax-codes", "tax_codes", "code", {"code": "1257L", "deduction_percentage": "0"}),
        ("payment-types", "payment_types", "name", {"name": "Hourly", "min_hourly_rate": "12"}),
        (
            "pay-bands",
            "pay_bands",
            "name",
            {"name": "Grade 3", "min_annual": "28000", "max_annual": "34000"},
        ),
        (
            "pay-schedules",
            "pay_schedules",
            "name",
            {
                "name": "Weekly Friday",
                "frequency": "weekly",
                "pay_day_kind": "weekday",
                "pay_day_value": 5,
            },
        ),
    ],
)
async def test_concurrent_creates_that_differ_only_in_case_save_one_and_refuse_one(
    rig: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    table: str,
    field: str,
    body: dict[str, Any],
) -> None:
    """ISS-39: both requests pass the name precheck; the unique index decides, as a 409."""
    import asyncio

    from app.modules.pay import router as pay_router

    async def passes(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(pay_router, "_free", passes)  # both are past the check at once
    admin = await rig["person"]("company_admin", rig["a"])
    upper = {**body, field: body[field].upper()}
    lower = {**body, field: body[field].lower()}
    answers = await asyncio.gather(
        admin.post(f"{API}/{path}", json=upper), admin.post(f"{API}/{path}", json=lower)
    )
    assert sorted(r.status_code for r in answers) == [201, 409], [r.text for r in answers]
    [refused] = [r for r in answers if r.status_code == 409]
    assert refused.json()["error"]["field"] == field
    async with rig["owner"].connect() as c:
        saved = (
            await c.execute(
                text(f"select count(*) from {table} where company_id = :c"),  # noqa: S608
                {"c": rig["a"]},
            )
        ).scalar_one()
    assert saved == 1
