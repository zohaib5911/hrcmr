"""T7.5: current source counts, urgent actions, readiness and filtered audit exports."""

from __future__ import annotations

import csv
import io
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from app.main import create_app
from app.modules.auth.sessions import SessionStore
from tests.db.api_support import sign_in_as, two_companies
from tests.db.support import DatabaseUnderTest, engine_for
from tests.support import TEST_REDIS_URL, build_settings

API = "/api/v1"


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
        yield {"person": person, "a": a, "b": b, "owner": owner, "app": app}
    for client in clients:
        await client.aclose()
    await owner.dispose()
    await redis.flushdb()
    await redis.aclose()


async def _employee(rig: dict[str, Any], company: uuid.UUID, name: str) -> uuid.UUID:
    ident = uuid.uuid4()
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "insert into employees (id,company_id,employee_number,first_name,last_name,email,hire_date) "
                "values (:i,:c,:n,:n,'Test','employee@example.com','2025-01-06')"
            ),
            {"i": ident, "c": company, "n": name},
        )
    return ident


async def _file(rig: dict[str, Any], company: uuid.UUID, *, clean: bool = True) -> uuid.UUID:
    ident = uuid.uuid4()
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "insert into files (id,company_id,storage_key,original_name,mime,size,sha256,scan_status) "
                "values (:i,:c,:k,'evidence.pdf','application/pdf',1,:sha,:scan)"
            ),
            {
                "i": ident,
                "c": company,
                "k": str(ident),
                "sha": "a" * 64,
                "scan": "clean" if clean else "pending",
            },
        )
    return ident


async def test_current_coverage_urgent_order_expiry_buckets_and_tenant_isolation(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    checker = next(
        u["user_id"] for u in (await admin.get(API + "/users")).json()["users"] if u["is_you"]
    )
    today = datetime.now(UTC).date()
    expected = {"Expired": -1, "Soon": 21, "Sixty": 60, "SixtyOne": 61, "Ninety": 90, "Future": 91}
    people = {
        name: await _employee(rig, rig["a"], name) for name in [*expected, "Missing", "Archived"]
    }
    await _employee(rig, rig["b"], "Foreign")
    evidence = await _file(rig, rig["a"])
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "update files set owner_type='employee',owner_id=:e,category='rtw_evidence' where id=:f"
            ),
            {"e": people["Soon"], "f": evidence},
        )
    for name, days in expected.items():
        result = await admin.post(
            f"{API}/employees/{people[name]}/rtw-checks",
            json={
                "check_type": "manual_list_b",
                "list_b_group": "group1",
                "permission_expires": True,
                "permission_expires_on": str(today + timedelta(days=days)),
                "check_date": str(today - timedelta(days=10)),
                "checked_by_user_id": checker,
                "outcome": "verified",
                "evidence_file_id": str(evidence) if name == "Soon" else None,
            },
        )
        assert result.status_code == 201, result.text
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update employees set status='archived' where id=:i"), {"i": people["Archived"]}
        )
    result = await admin.get(API + "/compliance/overview")
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["coverage"]["total"] == 7
    assert data["coverage"]["valid"] == 1
    counts = {c["status"]: c for c in data["coverage"]["counts"]}
    assert counts["expiring"]["count"] == 1
    assert counts["not_recorded"]["count"] == 1
    assert counts["expired"]["count"] == 1
    assert counts["expiring"]["href"] == "/employees?rtw=Expiring"
    assert data["attention"][0]["title"] == "Right to Work expired"
    assert [a["priority"] for a in data["attention"]] == sorted(
        a["priority"] for a in data["attention"]
    )
    assert "Foreign" not in result.text
    assert "Archived Test" not in result.text
    assert {e["days_left"]: e["bucket"] for e in data["expiring"]} == {
        -1: "overdue",
        21: "next_30",
        60: "31_60",
        61: "61_90",
        90: "61_90",
    }
    for role in ("company_admin", "hr_admin", "read_only_auditor"):
        assert (
            await (await rig["person"](role, rig["a"])).get(API + "/compliance/overview")
        ).status_code == 200
    for role in ("employee", "people_manager", "recruiter"):
        assert (
            await (await rig["person"](role, rig["a"])).get(API + "/compliance/overview")
        ).status_code == 403


async def test_readiness_clean_documents_required_roles_and_reporting_dates(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    initial = (await admin.get(API + "/compliance/overview")).json()
    checks = {c["id"]: c["status"] for c in initial["readiness"]}
    assert checks == {
        "profile": "incomplete",
        "key_personnel": "incomplete",
        "documents": "incomplete",
        "rtw": "not_applicable",
        "changes": "not_applicable",
    }
    proof = await _file(rig, rig["a"], clean=False)
    async with rig["owner"].begin() as c:
        await c.execute(
            text(
                "update companies set type_of_organisation='sole_proprietorship',sector='A', contact_email='hello@example.com',contact_phone='01234567890' where id=:c"
            ),
            {"c": rig["a"]},
        )
        await c.execute(
            text(
                "insert into locations (company_id,name,postcode,address_line1,city,is_default) values (:c,'Main','SW1A 1AA','1 Main Street','London',true)"
            ),
            {"c": rig["a"]},
        )
        for role in ("authorising_officer", "key_contact", "level1_user"):
            await c.execute(
                text(
                    "insert into key_persons (company_id,role,first_name,last_name) values (:c,:r,'Ann','Test')"
                ),
                {"c": rig["a"], "r": role},
            )
        await c.execute(
            text(
                "insert into company_compliance_documents (company_id,doc_type,file_id) values (:c,'employers_liability_insurance',:f)"
            ),
            {"c": rig["a"], "f": proof},
        )
    data = (await admin.get(API + "/compliance/overview")).json()
    checks = {c["id"]: c["status"] for c in data["readiness"]}
    assert checks["profile"] == checks["key_personnel"] == "complete"
    assert checks["documents"] == "incomplete"
    async with rig["owner"].begin() as c:
        await c.execute(text("update files set scan_status='clean' where id=:f"), {"f": proof})
        # Reporting cannot silently become ready while there is an outstanding prompt-report replacement.
        await c.execute(
            text(
                "insert into org_changes (company_id,change_type,change_date,calendar_region) values (:c,'ao_or_key_contact',current_date,'england-and-wales')"
            ),
            {"c": rig["a"]},
        )
    data = (await admin.get(API + "/compliance/overview")).json()
    checks = {c["id"]: c["status"] for c in data["readiness"]}
    assert checks["documents"] == "complete"
    assert checks["changes"] == "incomplete"
    assert any(
        a["title"] == "Replacement needs prompt reporting" and a["due_on"] is None
        for a in data["attention"]
    )


async def test_activity_category_cursor_export_match_and_formula_safety(
    rig: dict[str, Any],
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    events = [
        "employee.rtw_recorded",
        "employee.rtw_corrected",
        "employee.created",
        "attendance.recorded",
        "employee.sponsor_document_added",
        "compliance_document.added",
        "employee.change_logged",
        "company.change_reported",
    ]
    async with rig["owner"].begin() as c:
        for action in events:
            await c.execute(
                text(
                    "insert into audit_events (company_id,actor_type,action,summary) values (:c,'system',:a,'=HYPERLINK(unsafe)')"
                ),
                {"c": rig["a"], "a": action},
            )
        await c.execute(
            text(
                "insert into audit_events (company_id,actor_type,action,summary) values (:c,'system','employee.rtw_recorded','foreign')"
            ),
            {"c": rig["b"]},
        )
    for category, expected in (
        ("rtw", events[:2]),
        ("attendance", [events[3]]),
        ("documents", events[4:6]),
        ("changes", events[6:]),
    ):
        response = await admin.get(API + "/compliance/activity", params={"category": category})
        assert response.status_code == 200, response.text
        assert sorted(e["action"] for e in response.json()["items"]) == sorted(expected)
        export = await admin.get(API + "/compliance/activity.csv", params={"category": category})
        assert export.status_code == 200
        rows = list(csv.reader(io.StringIO(export.content.decode("utf-8-sig"))))
        assert sorted(r[2] for r in rows[1:]) == sorted(expected)
        assert all(r[4].startswith("'=HYPERLINK") for r in rows[1:])
        assert "foreign" not in export.text
    first = (
        await admin.get(API + "/compliance/activity", params={"category": "rtw", "limit": 1})
    ).json()
    second = (
        await admin.get(
            API + "/compliance/activity",
            params={"category": "rtw", "limit": 1, "cursor": first["next_cursor"]},
        )
    ).json()
    assert first["items"][0]["id"] != second["items"][0]["id"]
    assert second["next_cursor"] is None
    hr = await rig["person"]("hr_admin", rig["a"])
    auditor = await rig["person"]("read_only_auditor", rig["a"])
    own = await rig["person"]("employee", rig["a"])
    assert (await hr.get(API + "/compliance/activity")).status_code == 200
    assert (await hr.get(API + "/compliance/activity.csv")).status_code == 403
    assert (await auditor.get(API + "/compliance/activity.csv")).status_code == 200
    assert (await own.get(API + "/compliance/activity")).status_code == 403
