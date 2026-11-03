"""T7.3: regional deadlines, immutable snapshots, reported actor/date and isolation."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
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
from tests.db.test_files import S3_ACCESS, S3_BUCKET, S3_ENDPOINT, S3_SECRET
from tests.reporting_calendar import seed_reporting_calendar
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


TODAY = datetime(2026, 11, 3, tzinfo=UTC).date()


@pytest.fixture(autouse=True)
def _clock(monkeypatch: pytest.MonkeyPatch) -> None:
    async def today(access: object) -> Any:
        return TODAY

    monkeypatch.setattr("app.modules.compliance.router._today", today)


@pytest.fixture(autouse=True)
async def _calendar(rig: dict[str, Any]) -> None:
    await seed_reporting_calendar(rig["owner"])


async def test_deadline_preview_and_employee_snapshot_reporting(rig: dict[str, Any]) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    base = f"{API}/employees/{emp}/changes"
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update employees set nationality='British', phone='01234567890' where id=:i"),
            {"i": emp},
        )
    proof = await hr.post(
        f"{API}/employees/{emp}/sponsor-documents",
        json={"doc_type": "passport", "reference_number": "PASSPORT12345"},
    )
    assert proof.status_code == 201, proof.text
    doc = proof.json()["id"]
    defaults = (await hr.get(base + "/options")).json()
    assert defaults["nationality"] == "British"
    assert defaults["contact_number"] == "01234567890"
    assert defaults["documents"][0]["id"] == doc
    assert "PASSPORT12345" not in str(defaults)
    preview = await hr.get(
        f"{API}/compliance/reporting-deadline", params={"change_date": "2026-08-28"}
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["deadline_date"] == "2026-09-14"
    assert preview.json()["bank_holidays_excluded"] == ["2026-08-31"]
    body = {
        "change_type": "salary_reduced",
        "change_date": "2026-08-28",
        "employment_type": "full_time",
        "job_title": "Senior carer",
        "nationality": "British",
        "contact_number": "01234567890",
        "address": "1 High Street, London",
        "ack_inform_hr": True,
        "ack_home_office_interview": False,
        "documents_snapshot": [doc],
        "remarks": "Changed hours and pay",
    }
    made = await hr.post(base, json=body)
    assert made.status_code == 201, made.text
    record = made.json()
    assert record["deadline_date"] == "2026-09-14"
    assert record["status"] == "overdue"
    assert record["documents_snapshot"] == [doc]
    assert record["ack_home_office_interview"] is False
    assert (await hr.get(f"{API}/employees/{emp}")).json()["can_delete"] is False
    # Updating the source person/document does not rewrite the logged snapshot.
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update employees set nationality='Irish',phone='changed' where id=:i"), {"i": emp}
        )
    updated = await hr.post(
        f"{API}/sponsor-documents/{doc}/versions", json={"doc_type": "passport"}
    )
    assert updated.status_code == 201, updated.text
    listed = (await hr.get(base)).json()[0]
    assert listed["nationality"] == "British"
    assert listed["contact_number"] == "01234567890"
    assert listed["documents_snapshot"] == [doc]
    assert listed["documents"] == [{"id": doc, "doc_type": "passport", "version": 1}]
    assert (
        len(
            (
                await hr.get(
                    f"{API}/compliance/changes", params={"state": "overdue", "q": "Amira E1"}
                )
            ).json()
        )
        == 1
    )
    fixed = await hr.post(
        f"{API}/changes/{record['id']}/mark-reported",
        json={"reported_date": "2026-09-14", "reference": "SMS-123"},
    )
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["status"] == "reported"
    assert fixed.json()["reported_on_time"] is True
    assert fixed.json()["reported_reference"] == "SMS-123"
    assert fixed.json()["reporter_name"]
    assert fixed.json()["reported_by_user_id"]
    assert fixed.json()["report_recorded_at"]
    assert (await hr.get(f"{API}/compliance/changes", params={"state": "unreported"})).json() == []
    assert (
        await hr.post(
            f"{API}/changes/{record['id']}/mark-reported",
            json={"reported_date": "2026-09-15", "reference": "SMS-other"},
        )
    ).status_code == 409
    with pytest.raises(DBAPIError, match="immutable"):
        async with rig["owner"].begin() as c:
            await c.execute(
                text("update change_of_circumstances set job_title='rewritten' where id=:i"),
                {"i": uuid.UUID(record["id"])},
            )
    async with rig["owner"].connect() as c:
        events = (
            await c.execute(
                text("select action,after from audit_events where entity_id=:i"), {"i": emp}
            )
        ).all()
    assert "employee.change_logged" in str(events)
    assert "employee.change_reported" in str(events)
    assert "SMS-123" in str(events)


@pytest.mark.parametrize(
    ("region", "start", "expected"),
    [
        ("england-and-wales", "2026-07-31", "2026-08-14"),
        ("scotland", "2026-07-31", "2026-08-17"),
        ("northern-ireland", "2026-03-13", "2026-03-30"),
    ],
)
async def test_company_region_drives_deadline(
    rig: dict[str, Any], region: str, start: str, expected: str
) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update companies set bank_holiday_region=:r where id=:i"),
            {"i": rig["a"], "r": region},
        )
    emp = await _employee(rig, rig["a"], "E1")
    made = await hr.post(
        f"{API}/employees/{emp}/changes", json={"change_type": "other", "change_date": start}
    )
    assert made.status_code == 201, made.text
    assert made.json()["deadline_date"] == expected
    assert made.json()["calendar_region"] == region


async def test_calendar_coverage_and_unreported_snapshot_guards(rig: dict[str, Any]) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    other = await _employee(rig, rig["a"], "E2")
    base = f"{API}/employees/{emp}/changes"
    body = {"change_type": "other", "change_date": "2026-10-30"}
    foreign_doc = await hr.post(
        f"{API}/employees/{other}/sponsor-documents", json={"doc_type": "other"}
    )
    assert (
        await hr.post(base, json={**body, "documents_snapshot": [foreign_doc.json()["id"]]})
    ).status_code == 404
    own_doc = await hr.post(
        f"{API}/employees/{emp}/sponsor-documents", json={"doc_type": "passport"}
    )
    ident = own_doc.json()["id"]
    assert (
        await hr.post(base, json={**body, "documents_snapshot": [ident, ident]})
    ).status_code == 409
    assert (await hr.post(base, json={**body, "change_date": "2026-11-04"})).status_code == 409
    assert (await hr.post(base, json={**body, "change_type": "unknown"})).status_code == 422
    assert (await hr.post(base, json={**body, "deadline_date": "2030-01-01"})).status_code == 422
    result = await hr.post(base, json=body)
    assert result.status_code == 201, result.text
    assert result.json()["status"] == "unreported"
    assert result.json()["working_days_left"] == 8
    with pytest.raises(DBAPIError, match="immutable"):
        async with rig["owner"].begin() as c:
            await c.execute(
                text("update change_of_circumstances set address='rewritten' where id=:i"),
                {"i": uuid.UUID(result.json()["id"])},
            )
    path = f"{API}/changes/{result.json()['id']}/mark-reported"
    for day in ("2026-10-29", "2026-11-04"):
        assert (
            await hr.post(path, json={"reported_date": day, "reference": "SMS"})
        ).status_code == 409
    assert (
        await hr.post(path, json={"reported_date": "2026-11-03", "reference": " "})
    ).status_code == 422
    async with rig["owner"].begin() as c:
        await c.execute(text("delete from bank_holidays where region='england-and-wales'"))
    missing = await hr.post(base, json=body)
    assert missing.status_code == 503
    assert missing.json()["error"]["code"] == "BANK_HOLIDAYS_UNAVAILABLE"
    # Retained calculations still read without the live calendar; prompt reporting needs no fixed date.
    assert (await hr.get(base)).json()[0]["deadline_date"]
    prompt = await hr.post(
        f"{API}/compliance/org-changes",
        json={"change_type": "ao_or_key_contact", "change_date": "2026-10-30"},
    )
    assert prompt.status_code == 201, prompt.text
    assert prompt.json()["deadline_date"] is None
    assert prompt.json()["status"] == "prompt"


async def test_org_crud_reporting_and_company_timezone(rig: dict[str, Any]) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    base = f"{API}/compliance/org-changes"
    made = await hr.post(
        base, json={"change_type": "address", "change_date": "2026-08-28", "remarks": "New office"}
    )
    assert made.status_code == 201, made.text
    assert made.json()["deadline_date"] == "2026-09-28"
    ident = made.json()["id"]
    assert len((await hr.get(base, params={"state": "overdue"})).json()) == 1
    changed = await hr.put(
        base + "/" + ident,
        json={"change_type": "ownership", "change_date": "2026-09-01", "remarks": "Corrected date"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["deadline_date"] == "2026-09-29"
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update companies set timezone='Pacific/Auckland' where id=:i"), {"i": rig["a"]}
        )
    reported = await hr.post(
        base + "/" + ident + "/mark-reported",
        json={"reported_date": "2026-10-01", "reference": "SMS-ORG"},
    )
    assert reported.status_code == 200, reported.text
    assert reported.json()["reported_on_time"] is False
    assert reported.json()["reported_date"] == "2026-10-01"
    assert reported.json()["reported_at"].startswith("2026-09-30")  # midnight in company timezone
    assert (
        await hr.put(
            base + "/" + ident, json={"change_type": "address", "change_date": "2026-09-01"}
        )
    ).status_code == 409
    assert (
        await hr.request("DELETE", base + "/" + ident, json={"reason": "Wrong record"})
    ).status_code == 409
    archived = await hr.post(base, json={"change_type": "other", "change_date": "2026-10-30"})
    archive_id = archived.json()["id"]
    removed = await hr.request(
        "DELETE", base + "/" + archive_id, json={"reason": "Duplicate entry"}
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["archive_reason"] == "Duplicate entry"
    assert (await hr.get(base + "/" + archive_id)).status_code == 404
    assert len((await hr.get(base)).json()) == 1
    async with rig["owner"].connect() as c:
        assert (
            await c.execute(
                text("select archive_reason from org_changes where id=:i"),
                {"i": uuid.UUID(archive_id)},
            )
        ).scalar_one() == "Duplicate entry"


async def test_changes_are_role_and_tenant_scoped(rig: dict[str, Any]) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    other_hr = await rig["person"]("hr_admin", rig["b"])
    auditor = await rig["person"]("read_only_auditor", rig["a"])
    employee = await rig["person"]("employee", rig["a"])
    manager = await rig["person"]("people_manager", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    foreign = await _employee(rig, rig["b"], "E1")
    base = f"{API}/employees/{emp}/changes"
    body = {"change_type": "other", "change_date": "2026-10-30"}
    made = await hr.post(base, json=body)
    assert made.status_code == 201, made.text
    change = made.json()["id"]
    org = await hr.post(
        f"{API}/compliance/org-changes", json={"change_type": "name", "change_date": "2026-10-30"}
    )
    org_id = org.json()["id"]
    assert (await auditor.get(base)).status_code == 200
    assert (await auditor.get(f"{API}/compliance/changes")).status_code == 200
    assert (await auditor.get(f"{API}/compliance/org-changes")).status_code == 200
    for reader in (auditor, employee, manager):
        assert (await reader.post(base, json=body)).status_code == 403
        assert (
            await reader.post(
                f"{API}/changes/{change}/mark-reported",
                json={"reported_date": "2026-11-03", "reference": "SMS"},
            )
        ).status_code == 403
        assert (
            await reader.post(
                f"{API}/compliance/org-changes",
                json={"change_type": "name", "change_date": "2026-10-30"},
            )
        ).status_code == 403
    for reader in (employee, manager):
        assert (await reader.get(base)).status_code == 403
        assert (await reader.get(f"{API}/compliance/changes")).status_code == 403
    assert (await other_hr.get(base)).status_code == 404
    assert (await hr.post(f"{API}/employees/{foreign}/changes", json=body)).status_code == 404
    assert (await other_hr.get(f"{API}/compliance/changes")).json() == []
    assert (await other_hr.get(f"{API}/compliance/org-changes/{org_id}")).status_code == 404
    assert (
        await other_hr.put(
            f"{API}/compliance/org-changes/{org_id}",
            json={"change_type": "name", "change_date": "2026-10-30"},
        )
    ).status_code == 404
    assert (
        await other_hr.post(
            f"{API}/changes/{change}/mark-reported",
            json={"reported_date": "2026-11-03", "reference": "SMS"},
        )
    ).status_code == 404
    assert (
        await other_hr.post(
            f"{API}/compliance/org-changes/{org_id}/mark-reported",
            json={"reported_date": "2026-11-03", "reference": "SMS"},
        )
    ).status_code == 404
