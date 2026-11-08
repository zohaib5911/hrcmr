"""T2.6: events are written in the same transaction as the change, sensitive values are masked, the
API reads and exports the trail (a company sees only its own), and nothing can change it."""

from __future__ import annotations

import csv
import io
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from redis.asyncio import Redis
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from app.core.crypto import KeyRing, set_keyring
from app.db.ids import uuid7
from app.db.session import GlobalSession, TenantSession
from app.main import create_app
from app.modules.audit.models import AuditEvent
from app.modules.audit.router import csv_cell
from app.modules.audit.service import (
    MASKED,
    AuditContext,
    changed_fields,
    is_sensitive,
    mask,
    record,
)
from app.modules.auth.sessions import SessionStore
from app.modules.companies.models import Company
from tests.db.support import DatabaseUnderTest, engine_for
from tests.support import TEST_REDIS_URL, build_settings

# --- masking (no database) --------------------------------------------------------------------------


def test_sensitive_fields_are_masked_wherever_they_are_nested() -> None:
    before = {
        "name": "Ada",
        "ni_number": "AB123456C",
        "bank": {
            "sort_code": "12-34-56",
            "account_number": "12345678",
            "bank_name": "Example Bank",
        },
        "contacts": [{"phone": "0123", "passport_number": "P1234567"}],
        "password_hash": "$argon2id$...",
        "reset_token": "abc",
        "salary": 41700,
        "note": None,
    }
    masked = mask(before)
    assert masked["name"] == "Ada"
    assert masked["bank"]["bank_name"] == "Example Bank"
    assert masked["contacts"][0]["phone"] == "0123"
    for hidden in (
        masked["ni_number"],
        masked["bank"]["sort_code"],
        masked["bank"]["account_number"],
        masked["contacts"][0]["passport_number"],
        masked["password_hash"],
        masked["reset_token"],
        masked["salary"],
    ):
        assert hidden == MASKED
    assert "AB123456C" not in str(masked)
    assert "12345678" not in str(masked)
    assert before["ni_number"] == "AB123456C"  # the caller's data is untouched


def test_new_secret_looking_fields_are_masked_without_being_listed() -> None:
    assert all(
        is_sensitive(name) for name in ("backup_secret", "Api_Key", "mfa_secret", "token_hash")
    )
    assert not any(is_sensitive(name) for name in ("first_name", "department", "start_date"))


def test_unusual_values_become_json() -> None:
    from datetime import date
    from decimal import Decimal

    ident = uuid.uuid4()
    assert mask({"id": ident, "on": date(2026, 11, 2), "pay": Decimal("12.50")}) == {
        "id": str(ident),
        "on": "2026-11-02",
        "pay": "12.50",
    }


def test_changed_fields_compares_the_real_values() -> None:
    assert changed_fields({"a": 1, "b": 2, "c": 3}, {"a": 1, "b": 9, "d": 4}) == ["b", "c", "d"]
    assert changed_fields({"ni_number": "X"}, {"ni_number": "Y"}) == [
        "ni_number"
    ]  # seen, not shown


def test_spreadsheet_formulas_are_neutralised() -> None:
    assert csv_cell("=1+1") == "'=1+1"
    assert csv_cell("@SUM(A1)") == "'@SUM(A1)"
    assert csv_cell("-2") == "'-2"
    assert csv_cell(None) == ""
    assert csv_cell("fine") == "fine"


# --- the service against the database -------------------------------------------------------------


@pytest.fixture(autouse=True)
def _keys() -> Iterator[None]:
    set_keyring(KeyRing(keys={"k1": os.urandom(32)}, active_kid="k1", blind_key=os.urandom(32)))
    yield
    set_keyring(None)


async def _two_companies(database: DatabaseUnderTest) -> tuple[uuid.UUID, uuid.UUID]:
    a, b = uuid7(), uuid7()
    owner = engine_for(database.owner_url, poolclass=NullPool)
    async with owner.begin() as c:
        await c.execute(text("truncate users, companies cascade"))
        for ident, slug in ((a, "a"), (b, "b")):
            await c.execute(
                text(
                    "insert into companies (id, name, slug, plan, subscription_status) "
                    "values (:i, :n, :s, 'annual', 'active')"
                ),
                {"i": ident, "n": f"Company {slug}", "s": slug},
            )
    await owner.dispose()
    return a, b


async def _count(database: DatabaseUnderTest, company: uuid.UUID, action: str) -> int:
    engine = engine_for(database.app_url, poolclass=NullPool)
    try:
        async with TenantSession(engine, company_id=company) as db:
            rows = await db.execute(
                select(AuditEvent.id).where(
                    AuditEvent.company_id == company, AuditEvent.action == action
                )
            )
            return len(rows.all())
    finally:
        await engine.dispose()


async def _name(database: DatabaseUnderTest, company: uuid.UUID) -> str:
    owner = engine_for(database.owner_url, poolclass=NullPool)
    async with owner.connect() as c:
        name = (
            await c.execute(text("select name from companies where id = :i"), {"i": company})
        ).scalar_one()
    await owner.dispose()
    return str(name)


async def test_an_event_and_the_change_it_describes_commit_or_vanish_together(
    database: DatabaseUnderTest,
) -> None:
    a, _ = await _two_companies(database)
    engine = engine_for(database.app_url, poolclass=NullPool)
    context = AuditContext(
        company_id=a, actor_user_id=None, actor_type="system", request_id="req-1"
    )

    async def rename(db: TenantSession, name: str, action: str) -> None:
        await db.execute(update(Company).where(Company.id == a).values(name=name))
        await record(
            db,
            context,
            action,
            entity_type="company",
            entity_id=a,
            before={"name": "x"},
            after={"name": name},
            reason="tidy-up",
        )

    try:
        # Both committed.
        async with TenantSession(engine, company_id=a) as db:
            await rename(db, "Renamed", "company.renamed")
            await db.commit()
        assert await _name(database, a) == "Renamed"
        assert await _count(database, a, "company.renamed") == 1

        # The business change fails after the event was added: neither is kept.
        async def business_change_fails() -> None:
            async with TenantSession(engine, company_id=a) as db:
                await rename(db, "Nope", "company.renamed.again")
                raise RuntimeError("the business change failed")

        with pytest.raises(RuntimeError):
            await business_change_fails()
        assert await _name(database, a) == "Renamed"
        assert await _count(database, a, "company.renamed.again") == 0

        # The event cannot be written (an action longer than the column allows): the change that
        # came with it is not kept either.
        async def event_cannot_be_written() -> None:
            async with TenantSession(engine, company_id=a) as db:
                await rename(db, "Nope too", "x" * 101)
                await db.commit()

        with pytest.raises(DBAPIError):
            await event_cannot_be_written()
        assert await _name(database, a) == "Renamed"

        with pytest.raises(ValueError, match="actor type"):
            await record(
                TenantSession(engine, company_id=a),
                AuditContext(company_id=a, actor_user_id=None, actor_type="robot"),
                "x.y",
            )
    finally:
        await engine.dispose()


async def test_stored_events_hold_no_raw_sensitive_values(database: DatabaseUnderTest) -> None:
    a, _ = await _two_companies(database)
    engine = engine_for(database.app_url, poolclass=NullPool)
    try:
        async with TenantSession(engine, company_id=a) as db:
            await record(
                db,
                AuditContext(company_id=a, actor_user_id=None, actor_type="system"),
                "employee.updated",
                before={"ni_number": "AB123456C", "first_name": "Ada"},
                after={"ni_number": "ZZ999999Z", "first_name": "Ada"},
            )
            await db.commit()
    finally:
        await engine.dispose()
    owner = engine_for(database.owner_url, poolclass=NullPool)
    async with owner.connect() as c:
        stored = (
            await c.execute(
                text(
                    "select before::text, after::text, summary from audit_events "
                    "where company_id = :a"
                ),
                {"a": a},
            )
        ).one()
    await owner.dispose()
    assert "AB123456C" not in stored[0]
    assert "ZZ999999Z" not in stored[1]
    assert stored[2] == "Changed: ni_number"


async def test_the_orm_cannot_change_or_remove_an_event_either(database: DatabaseUnderTest) -> None:
    a, _ = await _two_companies(database)
    engine = engine_for(database.app_url, poolclass=NullPool)
    try:
        async with TenantSession(engine, company_id=a) as db:
            event = await record(
                db, AuditContext(company_id=a, actor_user_id=None, actor_type="system"), "x.y"
            )
            await db.commit()
            event.summary = "rewritten"
            with pytest.raises(DBAPIError):
                await db.commit()
        async with TenantSession(engine, company_id=a) as db:
            stored = (await db.execute(select(AuditEvent))).scalars().one()
            await db.delete(stored)
            with pytest.raises(DBAPIError):
                await db.commit()
    finally:
        await engine.dispose()


# --- the endpoints ---------------------------------------------------------------------------------------


@pytest.fixture
async def api(database: DatabaseUnderTest) -> AsyncIterator[dict[str, Any]]:
    redis = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    await redis.flushdb()
    a, b = await _two_companies(database)
    settings = build_settings(database_url=database.app_url, redis_url=TEST_REDIS_URL)
    app = create_app(settings)
    sessions = SessionStore(redis)

    async def person(role: str, company: uuid.UUID) -> httpx.AsyncClient:
        user = uuid7()
        owner = engine_for(database.owner_url, poolclass=NullPool)
        async with owner.begin() as c:
            await c.execute(
                text(
                    "insert into users (id, email, first_name, last_name, password_hash, email_verified_at) "
                    "values (:u, :e, 'Ann', :r, 'x', now())"
                ),
                {"u": user, "e": f"{role}-{user}@example.com", "r": role},
            )
            await c.execute(
                text("insert into memberships (user_id, company_id, role) values (:u, :c, :r)"),
                {"u": user, "c": company, "r": role},
            )
            await c.execute(
                text(
                    "insert into terms_acceptances (user_id, version) select :u, version from terms_versions"
                ),
                {"u": user},
            )
        await owner.dispose()
        engine = engine_for(database.app_url, poolclass=NullPool)
        async with GlobalSession(engine) as db:
            token, _ = await sessions.create(
                db, user_id=user, company_id=company, ip=None, user_agent=None, mfa_passed=True
            )
            await db.commit()
        await engine.dispose()
        browser = httpx.AsyncClient(transport=transport, base_url="http://test")
        browser.cookies.set("brand_session", token)
        browser.cookies.set("csrf", "t")
        browser.headers["X-CSRF-Token"] = "t"
        browser.user = user  # type: ignore[attr-defined]
        return browser

    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        yield {"person": person, "a": a, "b": b, "db": database}
    await redis.flushdb()
    await redis.aclose()


async def _add_events(database: DatabaseUnderTest, company: uuid.UUID, n: int, prefix: str) -> None:
    engine = engine_for(database.app_url, poolclass=NullPool)
    try:
        async with TenantSession(engine, company_id=company) as db:
            for i in range(n):
                await record(
                    db,
                    AuditContext(
                        company_id=company,
                        actor_user_id=None,
                        actor_type="system",
                        ip="203.0.113.9",
                    ),
                    f"{prefix}.{i}",
                    entity_type="thing",
                    after={"n": i, "note": "=HYPERLINK(1)" if i == 0 else "ok"},
                )
            await db.commit()
    finally:
        await engine.dispose()


async def test_the_trail_is_listed_filtered_paged_and_scoped_to_the_company(
    api: dict[str, Any],
) -> None:
    a, b, db = api["a"], api["b"], api["db"]
    await _add_events(db, a, 5, "employee.edit")
    await _add_events(db, a, 2, "leave.approve")
    await _add_events(db, b, 3, "employee.edit")  # another company's, never visible to a
    auditor = await api["person"]("read_only_auditor", a)
    async with auditor:
        first = await auditor.get("/api/v1/audit-events?limit=3")
        assert first.status_code == 200
        page = first.json()
        assert len(page["items"]) == 3
        assert page["next_cursor"]
        second = (
            await auditor.get(f"/api/v1/audit-events?limit=3&cursor={page['next_cursor']}")
        ).json()
        third = (
            await auditor.get(f"/api/v1/audit-events?limit=3&cursor={second['next_cursor']}")
        ).json()
        ids = [e["id"] for p in (page, second, third) for e in p["items"]]
        assert len(ids) == len(set(ids)) == 7  # every one of company a's events, once
        assert third["next_cursor"] is None

        only = (await auditor.get("/api/v1/audit-events?action=leave.")).json()["items"]
        assert [e["action"] for e in only] == ["leave.approve.1", "leave.approve.0"]  # newest first
        assert only[0]["ip"] == "203.0.113.9"
        assert (await auditor.get("/api/v1/audit-events?cursor=nonsense")).status_code == 422
        assert (await auditor.get("/api/v1/audit-events?limit=500")).status_code == 422


async def test_only_those_who_may_read_or_export_can(api: dict[str, Any]) -> None:
    a = api["a"]
    for role, read, export in (
        ("company_admin", 200, 200),
        ("hr_admin", 200, 403),  # may read the trail but not export it
        ("read_only_auditor", 200, 200),
        ("people_manager", 403, 403),
        ("employee", 403, 403),
        ("recruiter", 403, 403),
    ):
        browser = await api["person"](role, a)
        async with browser:
            assert (await browser.get("/api/v1/audit-events")).status_code == read, role
            assert (await browser.get("/api/v1/audit-events.csv")).status_code == export, role


async def test_the_export_is_a_safe_spreadsheet_and_is_itself_recorded(api: dict[str, Any]) -> None:
    a, db = api["a"], api["db"]
    await _add_events(db, a, 3, "export.test")
    admin = await api["person"]("company_admin", a)
    async with admin:
        response = await admin.get("/api/v1/audit-events.csv?action=export.test")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "attachment" in response.headers["content-disposition"]
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        assert rows[0][:3] == ["Time (UTC)", "Who", "Action"]
        # Events written in one transaction share a timestamp, so their order among themselves is not fixed.
        assert sorted(r[2] for r in rows[1:]) == ["export.test.0", "export.test.1", "export.test.2"]
        listed = (await admin.get("/api/v1/audit-events?action=audit.exported")).json()["items"]
        assert listed[0]["summary"] == "Exported 3 events"
        assert listed[0]["actor_name"] == "Ann company_admin"
