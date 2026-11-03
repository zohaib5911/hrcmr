"""T7.1: RTW versions, encrypted codes, derived status, evidence and isolation."""

from __future__ import annotations

import io
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from pypdf import PdfReader
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from app.core.crypto import KeyRing, set_keyring
from app.db.rtw import employee_rtw_status
from app.db.session import TenantSession
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


CODE = "W12345678"


async def _checker(hr: httpx.AsyncClient) -> str:
    users = (await hr.get(f"{API}/users")).json()["users"]
    return str(next(user["user_id"] for user in users if user["is_you"]))


async def _proof(hr: httpx.AsyncClient, emp: uuid.UUID) -> str:
    made = await hr.post(
        f"{API}/employees/{emp}/documents",
        files={"file": ("rtw.pdf", PDF, "application/pdf")},
        data={"category": "rtw_evidence"},
    )
    assert made.status_code == 201, made.text
    return str(made.json()["file_id"])


async def test_record_replace_correct_historical_and_export_keep_codes_masked(
    rig: dict[str, Any],
) -> None:
    hr = await rig["person"]("company_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    base = f"{API}/employees/{emp}/rtw-checks"
    assert (await hr.get(base)).json()["status"] == "not_recorded"
    checker = await _checker(hr)
    evidence = await _proof(hr, emp)
    today = datetime.now(UTC).date()
    body = {
        "check_type": "online_share_code",
        "share_code": CODE,
        "permission_expires": True,
        "permission_expires_on": str(today + timedelta(days=21)),
        "check_date": str(today),
        "checked_by_user_id": checker,
        "outcome": "verified",
        "evidence_file_id": evidence,
    }
    made = await hr.post(base, json=body)
    assert made.status_code == 201, made.text
    first = made.json()
    assert first["status"] == "expiring"
    assert first["follow_up_due_on"] == body["permission_expires_on"]
    assert first["share_code_masked"].endswith("678")
    assert CODE not in made.text
    assert "share_code" not in first
    next_check = await hr.post(base, json={**body, "share_code": "W98765432"})
    assert next_check.status_code == 201, next_check.text
    current = next_check.json()["id"]
    fixed = await hr.post(
        f"{base}/{first['id']}/correct", json={**body, "reason": "Corrected the evidence reference"}
    )
    assert fixed.status_code == 201, fixed.text
    assert fixed.json()["superseded_at"] is not None  # historical correction never replaces current
    tab = (await hr.get(base)).json()
    assert tab["current"]["id"] == current
    assert len(tab["checks"]) == 3
    assert (
        await hr.post(f"{base}/{first['id']}/correct", json={**body, "reason": "Again"})
    ).status_code == 409
    corrected = await hr.post(
        f"{base}/{current}/correct",
        json={**body, "reason": "Corrected check result", "outcome": "pending"},
    )
    assert corrected.status_code == 201, corrected.text
    assert (await hr.get(base)).json()["status"] == "pending"
    assert (await hr.get(f"{API}/employees/{emp}")).json()["can_delete"] is False
    link = await hr.get(f"{base}/{first['id']}/evidence")
    assert link.json()["expires_in"] == 60
    pdf = await hr.get(f"{base}/{first['id']}/evidence.pdf")
    assert pdf.status_code == 200
    output = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf.content)).pages)
    assert "Right to Work evidence sheet" in output
    assert "rtw.pdf" in output
    assert CODE not in output
    full = await hr.get(f"{API}/employees/{emp}/record.pdf")
    assert full.status_code == 200
    full_text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(full.content)).pages)
    assert "Right to Work history" in full_text
    assert CODE not in full_text
    assert "W98765432" not in output
    async with rig["owner"].connect() as c:
        stored = (
            await c.execute(
                text("select share_code from rtw_checks where id=:i"), {"i": uuid.UUID(first["id"])}
            )
        ).scalar_one()
        audit = (
            (
                await c.execute(
                    text("select after::text from audit_events where entity_id=:i"), {"i": emp}
                )
            )
            .scalars()
            .all()
        )
    assert stored.startswith("v1:")
    assert CODE not in stored
    assert not any(CODE in (v or "") or "W98765432" in (v or "") for v in audit)
    async with rig["owner"].begin() as c:
        with pytest.raises(DBAPIError, match="immutable"):
            await c.execute(
                text("update rtw_checks set outcome='failed' where id=:i"),
                {"i": uuid.UUID(first["id"])},
            )


async def test_conditional_fields_dates_checker_evidence_and_permissions(
    rig: dict[str, Any],
) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    other = await _employee(rig, rig["a"], "E2")
    foreign = await _employee(rig, rig["b"], "E1")
    foreign_hr = await rig["person"]("hr_admin", rig["b"])
    base = f"{API}/employees/{emp}/rtw-checks"
    checker = await _checker(hr)
    common = {"check_date": str(datetime.now(UTC).date()), "checked_by_user_id": checker}
    for fields in (
        {"check_type": "online_share_code"},
        {"check_type": "online_share_code", "share_code": "123"},
        {"check_type": "manual_list_a", "share_code": CODE},
        {"check_type": "manual_list_b", "list_b_group": "group1"},
        {"check_type": "idsp_digital", "idsp_provider": "Provider"},
        {"check_type": "idsp_digital", "idsp_provider": " ", "idsp_document": "british_passport"},
        {"check_type": "manual_list_a", "permission_expires_on": "2030-01-01"},
    ):
        assert (await hr.post(base, json={**common, **fields})).status_code == 422, fields
    body = {**common, "check_type": "manual_list_a", "outcome": "verified"}
    assert (await hr.post(base, json={**body, "check_date": "2999-01-01"})).status_code == 409
    assert (
        await hr.post(base, json={**body, "checked_by_user_id": await _checker(foreign_hr)})
    ).status_code == 404
    assert (
        await hr.post(base, json={**body, "evidence_file_id": await _proof(hr, other)})
    ).status_code == 404
    valid = await hr.post(base, json=body)
    assert valid.status_code == 201
    assert valid.json()["status"] == "evidence_missing"
    check_id = valid.json()["id"]
    assert (
        await hr.post(f"{base}/{check_id}/correct", json={**body, "reason": "Fix"})
    ).status_code == 403
    admin = await rig["person"]("company_admin", rig["a"])
    assert (
        await admin.post(f"{base}/{check_id}/correct", json={**body, "reason": " "})
    ).status_code == 422
    idsp = await hr.post(
        base,
        json={
            **common,
            "check_type": "idsp_digital",
            "idsp_provider": "Certified provider",
            "idsp_document": "irish_passport_card",
        },
    )
    assert idsp.status_code == 201, idsp.text
    me = await rig["person"]("employee", rig["a"])
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update memberships set employee_id=:e where company_id=:c and role='employee'"),
            {"e": emp, "c": rig["a"]},
        )
    assert (await me.get(base)).status_code == 200
    assert (await me.get(f"{API}/employees/{other}/rtw-checks")).status_code == 404
    for client in (me, await rig["person"]("people_manager", rig["a"])):
        assert (await client.post(base, json=body)).status_code == 403
        assert (
            await client.post(f"{base}/{check_id}/correct", json={**body, "reason": "Fix"})
        ).status_code == 403
        assert (await client.get(f"{base}/{check_id}/evidence.pdf")).status_code == 403
    assert (await hr.get(f"{API}/employees/{foreign}/rtw-checks")).status_code == 404
    assert (await hr.post(f"{API}/employees/{foreign}/rtw-checks", json=body)).status_code == 404
    for suffix in ("correct", "evidence", "evidence.pdf"):
        path = f"{API}/employees/{other}/rtw-checks/{check_id}/{suffix}"
        response = (
            await admin.post(path, json={**body, "reason": "Fix"})
            if suffix == "correct"
            else await hr.get(path)
        )
        assert response.status_code == 404


@pytest.mark.parametrize(
    ("outcome", "days", "proof", "expected"),
    [
        ("failed", None, False, "failed"),
        ("pending", None, False, "pending"),
        ("verified", None, False, "evidence_missing"),
        ("verified", None, True, "verified"),
        ("verified", 61, True, "verified"),
        ("verified", 60, True, "expiring"),
        ("verified", 21, True, "expiring"),
        ("verified", 0, True, "expiring"),
        ("verified", -1, True, "expired"),
    ],
)
async def test_derived_view_boundaries_and_tenant_isolation(
    rig: dict[str, Any], outcome: str, days: int | None, proof: bool, expected: str
) -> None:
    hr = await rig["person"]("hr_admin", rig["a"])
    emp = await _employee(rig, rig["a"], "E1")
    await _employee(rig, rig["b"], "E1")
    body: dict[str, Any] = {
        "check_type": "manual_list_a",
        "check_date": str(datetime.now(UTC).date()),
        "checked_by_user_id": await _checker(hr),
        "outcome": outcome,
    }
    if days is not None:
        body.update(
            check_type="manual_list_b",
            list_b_group="group2",
            permission_expires=True,
            permission_expires_on=str(datetime.now(UTC).date() + timedelta(days=days)),
        )
    if proof:
        body["evidence_file_id"] = await _proof(hr, emp)
    result = await hr.post(f"{API}/employees/{emp}/rtw-checks", json=body)
    assert result.status_code == 201, result.text
    assert result.json()["status"] == expected
    assert (await hr.get(f"{API}/employees/{emp}/rtw-checks")).json()["status"] == expected
    listing = (await hr.get(f"{API}/employees")).json()
    assert listing["employees"][0]["rtw_status"] == expected
    link_status = {
        "verified": "Verified",
        "expiring": "Expiring",
        "expired": "Expired",
        "failed": "Expired",
        "pending": "Pending",
        "evidence_missing": "EvidenceMissing",
    }[expected]
    filtered = (await hr.get(f"{API}/employees", params={"rtw": link_status})).json()
    assert len(filtered["employees"]) == 1
    needs = (await hr.get(f"{API}/employees", params={"rtw": "NeedsAttention"})).json()
    assert len(needs["employees"]) == (0 if expected == "verified" else 1)
    summary = (await hr.get(f"{API}/employees/summary")).json()
    assert summary["rtw_needs_attention"] == (0 if expected == "verified" else 1)
    assert (await hr.get(f"{API}/employees/{emp}")).json()["rtw_status"] == expected
    if days is None and proof and expected == "verified":
        async with rig["owner"].begin() as c:
            await c.execute(
                text("update files set scan_status='pending' where id=:i"),
                {"i": uuid.UUID(body["evidence_file_id"])},
            )
        assert (await hr.get(f"{API}/employees/{emp}/rtw-checks")).json()[
            "status"
        ] == "evidence_missing"
        assert (
            await hr.get(f"{API}/employees/{emp}/rtw-checks/{result.json()['id']}/evidence")
        ).status_code == 404
    engine = engine_for(rig["db"].app_url, poolclass=NullPool)
    try:
        async with TenantSession(engine, company_id=rig["a"]) as db:
            rows = (await db.execute(select(employee_rtw_status.c.employee_id))).scalars().all()
            assert rows == [emp]  # view cannot use owner privileges to expose the other tenant
    finally:
        await engine.dispose()


@pytest.mark.parametrize("timezone", ["Europe/London", "Pacific/Kiritimati", "America/Los_Angeles"])
async def test_python_and_sql_rtw_status_match_on_identical_rows(
    rig: dict[str, Any],
    timezone: str,
) -> None:
    from datetime import date
    from itertools import product

    from app.modules.employees.models import Employee
    from app.modules.files.models import File
    from app.modules.rtw.models import RTWCheck
    from app.modules.rtw.router import status_of

    hr = await rig["person"]("hr_admin", rig["a"])
    checker = uuid.UUID(await _checker(hr))
    async with rig["owner"].begin() as connection:
        await connection.execute(
            text("update companies set timezone=:tz where id=:c"), {"tz": timezone, "c": rig["a"]}
        )
    engine = engine_for(rig["db"].app_url, poolclass=NullPool)
    try:
        async with TenantSession(engine, company_id=rig["a"]) as db:
            # CURRENT_TIMESTAMP is transaction-stable: Python gets exactly the SQL view's date.
            today = (
                await db.execute(
                    text("select (CURRENT_TIMESTAMP AT TIME ZONE :tz)::date"), {"tz": timezone}
                )
            ).scalar_one()
            cases = []
            for outcome, days, scan in product(
                ("verified", "pending", "failed"),
                (None, -1, 0, 60, 61),
                (None, "pending", "clean", "infected", "error"),
            ):
                emp = Employee(
                    id=uuid.uuid4(),
                    employee_number=str(uuid.uuid4()),
                    first_name="Status",
                    last_name="Parity",
                    email="parity@example.com",
                    hire_date=date(2025, 1, 1),
                )
                db.add(emp)
                proof = None
                if scan is not None:
                    proof = File(
                        id=uuid.uuid4(),
                        storage_key=str(uuid.uuid4()),
                        original_name="proof.pdf",
                        mime="application/pdf",
                        size=1,
                        sha256="a" * 64,
                        scan_status=scan,
                    )
                    db.add(proof)
                await db.flush()
                check = RTWCheck(
                    id=uuid.uuid4(),
                    subject_type="employee",
                    subject_id=emp.id,
                    check_type="manual_list_a" if days is None else "manual_list_b",
                    list_b_group=None if days is None else "group1",
                    permission_expires=days is not None,
                    permission_expires_on=None if days is None else today + timedelta(days=days),
                    check_date=today,
                    checked_by_user_id=checker,
                    outcome=outcome,
                    evidence_file_id=proof.id if proof else None,
                )
                db.add(check)
                await db.flush()  # read the database-generated follow_up_due_on
                cases.append((emp.id, check, scan, outcome, days))
            missing = Employee(
                id=uuid.uuid4(),
                employee_number="NO-CHECK",
                first_name="No",
                last_name="Check",
                email="none@example.com",
                hire_date=date(2025, 1, 1),
            )
            db.add(missing)
            await db.flush()
            sql_statuses = dict(
                (
                    await db.execute(
                        select(employee_rtw_status.c.employee_id, employee_rtw_status.c.status)
                    )
                ).all()
            )
            assert sql_statuses[missing.id] == "not_recorded"
            assert len(sql_statuses) == 76
            for employee_id, check, scan, outcome, days in cases:
                python_status = status_of(check, today, clean_evidence=scan == "clean")
                assert python_status == sql_statuses[employee_id], (timezone, outcome, days, scan)
    finally:
        await engine.dispose()
