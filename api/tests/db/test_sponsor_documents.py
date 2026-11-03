"""T7.2: sponsor document versions, masked references, renewals and sponsored register."""

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


REFERENCE = "VISA-123456789"
COS = "COS-987654321"


async def _proof(client: httpx.AsyncClient, emp: uuid.UUID) -> str:
    result = await client.post(
        f"{API}/employees/{emp}/documents",
        files={"file": ("sponsor.pdf", PDF, "application/pdf")},
        data={"category": "id_document"},
    )
    assert result.status_code == 201, result.text
    return str(result.json()["file_id"])


async def test_versions_renewal_withdrawal_encryption_and_immutable_history(
    rig: dict[str, Any],
) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    base = f"{API}/employees/{emp}/sponsor-documents"
    today = datetime.now(UTC).date()
    expiry = str(today + timedelta(days=120))
    body = {
        "doc_type": "visa",
        "visa_route": "skilled_worker",
        "reference_number": REFERENCE,
        "cos_number": COS,
        "issuing_country": "gb",
        "soc_code": "6135",
        "sponsored_salary": "32000.00",
        "expiry_date": expiry,
        "evidence_file_id": await _proof(hr, emp),
    }
    assert (await hr.get(base)).json() == []
    made = await hr.post(base, json=body)
    assert made.status_code == 201, made.text
    first = made.json()
    assert first["version"] == 1
    assert first["status"] == "current"
    assert first["issuing_country"] == "GB"
    assert first["sponsored_salary"] == "32000.00"
    assert REFERENCE not in made.text
    assert COS not in made.text
    assert first["reference_number_masked"].endswith("789")
    assert first["cos_number_masked"].endswith("321")
    assert (await hr.post(base, json=body)).status_code == 409
    path = f"{API}/sponsor-documents/{first['id']}"
    planned = await hr.post(
        path + "/renewal",
        json={"renewal_date": str(today + timedelta(days=30)), "notes": "Ask for renewed evidence"},
    )
    assert planned.status_code == 200, planned.text
    assert planned.json()["expiry_date"] == expiry
    assert planned.json()["version"] == 1
    updated = await hr.post(
        path + "/versions",
        json={
            **body,
            "reference_number": None,
            "cos_number": None,
            "expiry_date": str(today + timedelta(days=300)),
        },
    )
    assert updated.status_code == 201, updated.text
    second = updated.json()
    assert second["version"] == 2
    assert second["renewal_date"] is None
    assert second["reference_number_masked"] == first["reference_number_masked"]
    assert second["cos_number_masked"] == first["cos_number_masked"]
    history = (await hr.get(base)).json()
    assert history[1]["id"] == first["id"]
    assert history[1]["superseded_by"] == second["id"]
    assert history[1]["status"] == "superseded"
    for suffix, data in [
        ("versions", body),
        ("withdraw", {"reason": "Wrong record"}),
        ("renewal", {"renewal_date": str(today)}),
    ]:
        assert (await hr.post(path + "/" + suffix, json=data)).status_code == 409
    withdrawn = await hr.post(
        f"{API}/sponsor-documents/{second['id']}/withdraw", json={"reason": "Replaced after review"}
    )
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "withdrawn"
    assert withdrawn.json()["withdraw_reason"] == "Replaced after review"
    assert (await hr.get(f"{API}/compliance/sponsored-employees")).json()["employees"] == []
    again = await hr.post(base, json=body)
    assert again.json()["version"] == 3
    assert (await hr.get(f"{API}/employees/{emp}")).json()["can_delete"] is False
    async with rig["owner"].connect() as c:
        stored = (
            await c.execute(
                text("select reference_number,cos_number from sponsor_documents where id=:i"),
                {"i": uuid.UUID(first["id"])},
            )
        ).one()
        assert all(value.startswith("v1:") for value in stored)
        assert REFERENCE not in str(stored)
        assert COS not in str(stored)
        events = (
            await c.execute(
                text("select action, before, after, reason from audit_events where entity_id=:i"),
                {"i": emp},
            )
        ).all()
        assert "employee.sponsor_document_renewal_planned" in str(events)
        assert "Replaced after review" in str(events)
        assert REFERENCE not in str(events)
        assert COS not in str(events)
    with pytest.raises(DBAPIError, match="immutable"):
        async with rig["owner"].begin() as c:
            await c.execute(
                text("update sponsor_documents set remarks='changed' where id=:i"),
                {"i": uuid.UUID(first["id"])},
            )


@pytest.mark.parametrize(
    "route",
    [
        "skilled_worker",
        "health_care_worker",
        "global_business_mobility",
        "scale_up",
        "temporary_worker",
        "graduate",
        "student",
        "euss_settled",
        "euss_pre_settled",
        "family",
        "other",
    ],
)
async def test_register_uses_only_current_sponsored_routes(rig: dict[str, Any], route: str) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    result = await hr.post(
        f"{API}/employees/{emp}/sponsor-documents",
        json={"doc_type": "visa", "visa_route": route, "cos_number": COS, "soc_code": "6135"},
    )
    assert result.status_code == 201, result.text
    rows = (await hr.get(f"{API}/compliance/sponsored-employees")).json()["employees"]
    sponsored = route in {
        "skilled_worker",
        "health_care_worker",
        "global_business_mobility",
        "scale_up",
        "temporary_worker",
    }
    assert len(rows) == int(sponsored)
    if sponsored:
        assert rows[0]["rtw_status"] == "not_recorded"
        assert COS not in str(rows)
        async with rig["owner"].begin() as c:
            await c.execute(text("update employees set status='archived' where id=:i"), {"i": emp})
        assert (await hr.get(f"{API}/compliance/sponsored-employees")).json()["employees"] == []


async def test_types_validation_evidence_and_date_statuses(rig: dict[str, Any]) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    other = await _employee(rig, rig["a"], "E2")
    foreign = await _employee(rig, rig["b"], "E1")
    base = f"{API}/employees/{emp}/sponsor-documents"
    for body in [
        {"doc_type": "visa"},
        {"doc_type": "passport", "visa_route": "student"},
        {"doc_type": "visa", "visa_route": "unknown"},
        {"doc_type": "visa", "visa_route": "student", "soc_code": "123"},
        {"doc_type": "visa", "visa_route": "student", "sponsored_salary": "-1"},
        {"doc_type": "passport", "issuing_country": "UKK"},
        {"doc_type": "passport", "issue_date": "2026-02-02", "expiry_date": "2026-01-01"},
    ]:
        assert (await hr.post(base, json=body)).status_code == 422
    wrong_file = await _proof(hr, other)
    assert (
        await hr.post(base, json={"doc_type": "passport", "evidence_file_id": wrong_file})
    ).status_code == 404
    today = datetime.now(UTC).date()
    proof = await _proof(hr, emp)
    for kind, days, expected in [
        ("passport", 90, "expiring"),
        ("dbs", 91, "current"),
        ("euss", -1, "expired"),
        ("national_id", 0, "expiring"),
        ("other", None, "current"),
    ]:
        result = await hr.post(
            base,
            json={
                "doc_type": kind,
                "evidence_file_id": proof,
                "expiry_date": str(today + timedelta(days=days)) if days is not None else None,
            },
        )
        assert result.status_code == 201, result.text
        assert result.json()["status"] == expected
    doc = (await hr.get(base)).json()[0]
    path = f"{API}/sponsor-documents/{doc['id']}"
    link = await hr.get(path + "/evidence")
    assert link.status_code == 200
    assert link.json()["expires_in"] == 60
    assert (await hr.post(path + "/withdraw", json={"reason": "  "})).status_code == 422
    assert (
        await hr.post(path + "/renewal", json={"renewal_date": str(today - timedelta(days=1))})
    ).status_code == 409
    assert (
        await hr.post(
            path + "/versions",
            json={"doc_type": "other" if doc["doc_type"] != "other" else "passport"},
        )
    ).status_code == 409
    assert (await hr.get(f"{API}/employees/{foreign}/sponsor-documents")).status_code == 404
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update files set scan_status='infected' where id=:i"), {"i": uuid.UUID(proof)}
        )
    assert (await hr.get(path + "/evidence")).status_code == 404
    assert (
        await hr.post(
            f"{API}/employees/{other}/sponsor-documents",
            json={"doc_type": "passport", "evidence_file_id": proof},
        )
    ).status_code == 404
    refreshed = (await hr.get(base)).json()
    assert next(r for r in refreshed if r["doc_type"] == "other")["status"] == "evidence_missing"


async def test_employee_own_read_auditor_and_tenant_isolation(rig: dict[str, Any]) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    other = await _employee(rig, rig["a"], "E2")
    foreign = await _employee(rig, rig["b"], "E1")
    base = f"{API}/employees/{emp}/sponsor-documents"
    body = {
        "doc_type": "visa",
        "visa_route": "skilled_worker",
        "sponsored_salary": "32000",
        "evidence_file_id": await _proof(hr, emp),
    }
    made = await hr.post(base, json=body)
    assert made.status_code == 201, made.text
    path = f"{API}/sponsor-documents/{made.json()['id']}"
    me = await rig["person"]("employee", rig["a"])
    auditor = await rig["person"]("read_only_auditor", rig["a"])
    manager = await rig["person"]("people_manager", rig["a"])
    stranger = await rig["person"]("hr_admin", rig["b"])
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update memberships set employee_id=:e where company_id=:c and role='employee'"),
            {"e": emp, "c": rig["a"]},
        )
    assert (await me.get(base)).json()[0]["sponsored_salary"] is None
    assert (await me.get(path + "/evidence")).status_code == 200
    assert (await me.get(f"{API}/employees/{other}/sponsor-documents")).status_code == 404
    assert (await auditor.get(base)).status_code == 200
    assert (await auditor.get(f"{API}/compliance/sponsored-employees")).status_code == 200
    assert (await manager.get(base)).status_code == 403
    for reader in (me, auditor, manager):
        assert (await reader.post(base, json=body)).status_code == 403
        for suffix, data in [
            ("versions", body),
            ("withdraw", {"reason": "Remove"}),
            ("renewal", {"renewal_date": str(datetime.now(UTC).date())}),
        ]:
            assert (await reader.post(path + "/" + suffix, json=data)).status_code == 403
    assert (await me.get(f"{API}/compliance/sponsored-employees")).status_code == 403
    assert (await hr.get(f"{API}/employees/{foreign}/sponsor-documents")).status_code == 404
    assert (await stranger.get(path + "/evidence")).status_code == 404
    assert (await stranger.post(path + "/withdraw", json={"reason": "Remove"})).status_code == 404
    assert (await stranger.post(path + "/versions", json=body)).status_code == 404
    assert (
        await stranger.post(path + "/renewal", json={"renewal_date": str(datetime.now(UTC).date())})
    ).status_code == 404
    assert (await stranger.get(f"{API}/compliance/sponsored-employees")).json()["employees"] == []
