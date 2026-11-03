"""T7.4: threshold scheduling, source lifecycle and daily calendar/status reconciliation."""

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
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from app.core.crypto import KeyRing, set_keyring
from app.main import create_app
from app.modules.auth.sessions import SessionStore
from tests.db.api_support import sign_in_as, two_companies
from tests.db.support import DatabaseUnderTest, engine_for
from tests.db.test_files import PDF, S3_ACCESS, S3_BUCKET, S3_ENDPOINT, S3_SECRET
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
    app = create_app(
        build_settings(
            database_url=database.app_url,
            redis_url=TEST_REDIS_URL,
            r2_endpoint=S3_ENDPOINT,
            r2_access_key_id=S3_ACCESS,
            r2_secret_access_key=S3_SECRET,
            r2_bucket_files=S3_BUCKET,
        )
    )
    sessions = SessionStore(redis)
    clients: list[httpx.AsyncClient] = []

    async def person(role: str, company: uuid.UUID) -> httpx.AsyncClient:
        client = await sign_in_as(database, sessions, app, role, company)
        clients.append(client)
        return client

    async with LifespanManager(app):
        yield {
            "person": person,
            "a": a,
            "b": b,
            "owner": owner,
            "app": app,
            "sessions": sessions,
            "db": database,
        }
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


async def _proof(client: httpx.AsyncClient, emp: uuid.UUID) -> str:
    made = await client.post(
        f"{API}/employees/{emp}/documents",
        files={"file": ("proof.pdf", PDF, "application/pdf")},
        data={"category": "rtw_evidence"},
    )
    assert made.status_code == 201, made.text
    return str(made.json()["file_id"])


async def _rows(rig: dict[str, Any], emp: uuid.UUID) -> list[dict[str, Any]]:
    async with rig["owner"].connect() as c:
        return list(
            (
                await c.execute(
                    text(
                        "select * from reminders where employee_id=:e order by sponsor_document_id,rtw_check_id,threshold_days"
                    ),
                    {"e": emp},
                )
            ).mappings()
        )  # type: ignore[return-value]


async def test_rtw_21_days_is_expiring_and_30_day_reminder_due_idempotently(
    rig: dict[str, Any],
) -> None:
    from app.jobs.compliance import reminders_daily, rtw_status_daily

    hr = await rig["person"]("hr_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    now = datetime.now(UTC)
    users = (await hr.get(f"{API}/users")).json()["users"]
    checker = next(user["user_id"] for user in users if user["is_you"])
    proof = await _proof(hr, emp)
    made = await hr.post(
        f"{API}/employees/{emp}/rtw-checks",
        json={
            "check_type": "online_share_code",
            "share_code": "W12345678",
            "permission_expires": True,
            "permission_expires_on": str(now.date() + timedelta(days=21)),
            "check_date": str(now.date()),
            "checked_by_user_id": checker,
            "outcome": "verified",
            "evidence_file_id": proof,
        },
    )
    assert made.status_code == 201, made.text
    assert made.json()["status"] == "expiring"
    rows = await _rows(rig, emp)
    assert len(rows) == 3
    thirty = next(row for row in rows if row["threshold_days"] == 30)
    assert thirty["status"] == "due"
    assert thirty["rtw_check_id"] == uuid.UUID(made.json()["id"])
    assert thirty["due_on"] == now.date() - timedelta(days=9)
    assert await reminders_daily({"owner_engine": rig["owner"], "now": now}) > 0
    assert await reminders_daily({"owner_engine": rig["owner"], "now": now}) == 0
    refreshed = await _rows(rig, emp)
    assert len(refreshed) == 3
    assert all(row["updated_by"] is None for row in refreshed)
    assert await rtw_status_daily({"owner_engine": rig["owner"]}) == 1
    async with rig["owner"].connect() as c:
        notices = (
            await c.execute(
                text(
                    "select title,body from notifications where company_id=:c and kind='compliance.reminders_due'"
                ),
                {"c": rig["a"]},
            )
        ).all()
        assert len(notices) == 1
        assert "Nothing has been sent" in notices[0].body
        assert "W12345678" not in str(notices)
    assert await reminders_daily({"owner_engine": None}) == 0
    assert await rtw_status_daily({"owner_engine": None}) == 0


async def test_document_versions_withdrawal_and_archive_restore_reconcile(
    rig: dict[str, Any],
) -> None:
    from app.jobs.compliance import reconcile_reminders

    hr = await rig["person"]("hr_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    now = datetime.now(UTC)
    body = {
        "doc_type": "visa",
        "visa_route": "skilled_worker",
        "expiry_date": str(now.date() + timedelta(days=120)),
    }
    made = await hr.post(f"{API}/employees/{emp}/sponsor-documents", json=body)
    assert made.status_code == 201, made.text
    first = made.json()["id"]
    rows = await _rows(rig, emp)
    assert len(rows) == 3
    assert {r["status"] for r in rows} == {"scheduled"}
    newer = await hr.post(
        f"{API}/sponsor-documents/{first}/versions",
        json={**body, "expiry_date": str(now.date() + timedelta(days=21))},
    )
    assert newer.status_code == 201, newer.text
    second = newer.json()["id"]
    rows = await _rows(rig, emp)
    assert len(rows) == 6
    assert {r["status"] for r in rows if r["sponsor_document_id"] == uuid.UUID(first)} == {
        "cancelled"
    }
    assert {r["status"] for r in rows if r["sponsor_document_id"] == uuid.UUID(second)} == {"due"}
    async with rig["owner"].begin() as c:
        await c.execute(text("update employees set status='archived' where id=:e"), {"e": emp})
    await reconcile_reminders(rig["owner"], now=now)
    rows = await _rows(rig, emp)
    assert {r["status"] for r in rows} == {"cancelled"}
    async with rig["owner"].begin() as c:
        await c.execute(text("update employees set status='active' where id=:e"), {"e": emp})
    await reconcile_reminders(rig["owner"], now=now)
    rows = await _rows(rig, emp)
    assert {r["status"] for r in rows if r["sponsor_document_id"] == uuid.UUID(second)} == {"due"}
    withdrawn = await hr.post(
        f"{API}/sponsor-documents/{second}/withdraw", json={"reason": "No longer current"}
    )
    assert withdrawn.status_code == 200, withdrawn.text
    assert {r["status"] for r in await _rows(rig, emp)} == {"cancelled"}


async def test_snooze_expiry_returns_to_due_and_notifies_once(rig: dict[str, Any]) -> None:
    from app.jobs.compliance import reconcile_reminders

    hr = await rig["person"]("hr_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    now = datetime.now(UTC)
    made = await hr.post(
        f"{API}/employees/{emp}/sponsor-documents",
        json={"doc_type": "passport", "expiry_date": str(now.date() + timedelta(days=21))},
    )
    assert made.status_code == 201, made.text
    await reconcile_reminders(rig["owner"], now=now)
    row = next(r for r in await _rows(rig, emp) if r["threshold_days"] == 30)
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update reminders set status='snoozed',snoozed_until=:u where id=:i"),
            {"i": row["id"], "u": now + timedelta(days=7)},
        )
    await reconcile_reminders(rig["owner"], now=now + timedelta(days=6))
    assert next(r for r in await _rows(rig, emp) if r["id"] == row["id"])["status"] == "snoozed"
    await reconcile_reminders(rig["owner"], now=now + timedelta(days=7))
    current = next(r for r in await _rows(rig, emp) if r["id"] == row["id"])
    assert current["status"] == "due"
    assert current["snoozed_until"] is None
    async with rig["owner"].connect() as c:
        assert (
            await c.execute(
                text(
                    "select count(*) from notifications where company_id=:c and kind='compliance.reminders_due'"
                ),
                {"c": rig["a"]},
            )
        ).scalar_one() == 2
    assert await reconcile_reminders(rig["owner"], now=now + timedelta(days=7)) == 0


async def test_daily_refresh_updates_only_unreported_derived_deadlines(rig: dict[str, Any]) -> None:
    from app.jobs.compliance import reconcile_reminders
    from tests.reporting_calendar import seed_reporting_calendar

    await seed_reporting_calendar(rig["owner"])
    hr = await rig["person"]("hr_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    made = await hr.post(
        f"{API}/employees/{emp}/changes",
        json={
            "change_type": "other",
            "change_date": "2026-08-28",
            "job_title": "Original snapshot",
        },
    )
    assert made.status_code == 201, made.text
    ident = uuid.UUID(made.json()["id"])
    assert made.json()["deadline_date"] == "2026-09-14"
    engine = engine_for(rig["db"].app_url, poolclass=NullPool)
    try:
        from app.db.session import TenantSession

        with pytest.raises(DBAPIError, match="immutable"):
            async with TenantSession(engine, company_id=rig["a"]) as db:
                await db.execute(
                    text(
                        "update change_of_circumstances set deadline_date='2026-09-15' where id=:i"
                    ),
                    {"i": ident},
                )
    finally:
        await engine.dispose()
    # A synthetic addition to the imported calendar exercises a later official-feed correction.
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "insert into bank_holidays (id,region,on_date,title,source,fetched_at) values (:i,'england-and-wales','2026-09-01','Additional holiday fixture','https://www.gov.uk/bank-holidays.json',now())"
            ),
            {"i": uuid.uuid4()},
        )
    await reconcile_reminders(rig["owner"])
    row = (await hr.get(f"{API}/employees/{emp}/changes")).json()[0]
    assert row["deadline_date"] == "2026-09-15"
    assert row["job_title"] == "Original snapshot"
    fixed = await hr.post(
        f"{API}/changes/{ident}/mark-reported",
        json={"reported_date": "2026-09-15", "reference": "SMS-1"},
    )
    assert fixed.status_code == 200, fixed.text
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "insert into bank_holidays (id,region,on_date,title,source,fetched_at) values (:i,'england-and-wales','2026-09-02','Second holiday fixture','https://www.gov.uk/bank-holidays.json',now())"
            ),
            {"i": uuid.uuid4()},
        )
    await reconcile_reminders(rig["owner"])
    assert (await hr.get(f"{API}/employees/{emp}/changes")).json()[0][
        "deadline_date"
    ] == "2026-09-15"


async def test_daily_due_dates_use_each_company_timezone(rig: dict[str, Any]) -> None:
    from app.jobs.compliance import reconcile_reminders

    east = await rig["person"]("hr_admin", rig["a"])
    west = await rig["person"]("hr_admin", rig["b"])
    a = await _employee(rig, rig["a"], "E1")
    b = await _employee(rig, rig["b"], "E1")
    moment = datetime(2026, 11, 3, 23, 30, tzinfo=UTC)
    due = datetime(2026, 11, 4, tzinfo=UTC).date()
    for client, emp in ((east, a), (west, b)):
        made = await client.post(
            f"{API}/employees/{emp}/sponsor-documents",
            json={"doc_type": "passport", "expiry_date": str(due + timedelta(days=90))},
        )
        assert made.status_code == 201, made.text
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update companies set timezone='Pacific/Auckland' where id=:i"), {"i": rig["a"]}
        )
        await c.execute(
            text("update companies set timezone='America/New_York' where id=:i"), {"i": rig["b"]}
        )
    await reconcile_reminders(rig["owner"], now=moment)
    assert next(r for r in await _rows(rig, a) if r["threshold_days"] == 90)["status"] == "due"
    assert (
        next(r for r in await _rows(rig, b) if r["threshold_days"] == 90)["status"] == "scheduled"
    )
