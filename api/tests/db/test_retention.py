"""Real retention job: exact cutoffs, isolation, shared files, failure/retry and idempotence."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.models import AiInteraction
from app.db.base import Base
from app.jobs.retention import anniversary, retention_purge_daily
from app.jobs.scheduled import SCHEDULE
from app.modules.audit.models import AuditEvent
from app.modules.exports.models import DataExport
from app.modules.identity.models import Session
from tests.db.test_employee_documents import _employee
from tests.db.test_employee_documents import _keys as _keys
from tests.db.test_employee_documents import rig as rig
from tests.db.test_exports import _document
from tests.db.test_rtw import _checker, _proof

NOW = datetime(2030, 3, 1, 2, tzinfo=UTC)


async def _count(rig: dict[str, Any], table: str, company: uuid.UUID) -> int:
    model = Base.metadata.tables[table]
    async with rig["owner"].connect() as c:
        return int(
            await c.scalar(
                select(func.count()).select_from(model).where(model.c.company_id == company)
            )
            or 0
        )


async def test_metadata_and_session_cutoffs_expired_archives_and_idempotence(
    rig: dict[str, Any],
) -> None:
    assert (
        next(job for job in SCHEDULE if job.name == "retention_purge_daily").job
        is retention_purge_daily
    )
    admin = await rig["person"]("company_admin", rig["a"])
    user = uuid.UUID(await _checker(admin))
    old_file, _ = await _document(rig, rig["a"], "expired.zip", "data_export")
    live_file, _ = await _document(rig, rig["a"], "live.zip", "data_export")
    async with AsyncSession(rig["owner"]) as db:
        for age in (30, 29):
            db.add(
                AiInteraction(
                    company_id=rig["a"],
                    user_id=user,
                    feature="letter",
                    model="m",
                    status="ok",
                    created_at=NOW - timedelta(days=age),
                )
            )
        for age in (90, 89):
            db.add(
                Session(
                    user_id=user,
                    company_id=rig["a"],
                    token_hash=uuid.uuid4().hex,
                    expires_at=NOW - timedelta(days=age),
                )
            )
        db.add(
            Session(
                user_id=user,
                company_id=rig["a"],
                token_hash=uuid.uuid4().hex,
                expires_at=NOW + timedelta(days=1),
                revoked_at=NOW - timedelta(days=90),
            )
        )
        for file, delta in ((old_file, 0), (live_file, 1)):
            db.add(
                DataExport(
                    company_id=rig["a"],
                    requested_by=user,
                    status="ready",
                    file_id=file,
                    finished_at=NOW - timedelta(days=7),
                    expires_at=NOW + timedelta(days=delta),
                )
            )
        await db.commit()
    ctx = {"owner_engine": rig["owner"], "storage": rig["app"].state.files.storage, "now": NOW}
    assert await retention_purge_daily(ctx) >= 4
    assert await _count(rig, "ai_interactions", rig["a"]) == 1
    async with rig["owner"].connect() as c:
        assert (
            await c.scalar(
                text("select count(*) from sessions where company_id=:c and expires_at < :now"),
                {"c": rig["a"], "now": NOW},
            )
            == 1
        )
        states = (
            await c.execute(
                text(
                    "select status, error_code from data_exports where company_id=:c order by expires_at nulls first"
                ),
                {"c": rig["a"]},
            )
        ).all()
        assert states == [("failed", "EXPIRED"), ("ready", None)]
        assert await c.scalar(text("select count(*) from files where id=:f"), {"f": old_file}) == 0
        assert await c.scalar(text("select count(*) from files where id=:f"), {"f": live_file}) == 1
    assert await retention_purge_daily(ctx) == 0


async def _evidence(
    rig: dict[str, Any],
    company: uuid.UUID,
    number: str,
    *,
    left: str | None,
    status: str = "leaver",
    visa_end: str | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    hr = await rig["person"]("company_admin", company)
    employee = await _employee(rig, company, number)
    checker = await _checker(hr)
    file = uuid.UUID(await _proof(hr, employee))
    # API creates two immutable versions pointing to the same evidence.
    for _ in range(2):
        made = await hr.post(
            f"/api/v1/employees/{employee}/rtw-checks",
            json={
                "check_type": "manual_list_a",
                "permission_expires": False,
                "check_date": "2026-01-01",
                "checked_by_user_id": checker,
                "outcome": "verified",
                "evidence_file_id": str(file),
            },
        )
        assert made.status_code == 201, made.text
    async with rig["owner"].begin() as c:
        await c.execute(
            text("update employees set status=:s, leave_date=cast(:d as date) where id=:e"),
            {"s": status, "d": date.fromisoformat(left) if left else None, "e": employee},
        )
        await c.execute(
            text(
                "insert into sponsor_documents (company_id,employee_id,doc_type,visa_route,expiry_date,evidence_file_id,version) values (:c,:e,'visa','skilled_worker',cast(:v as date),:f,1)"
            ),
            {
                "c": company,
                "e": employee,
                "f": file,
                "v": date.fromisoformat(visa_end) if visa_end else None,
            },
        )
    return employee, file


async def test_evidence_calendar_cutoffs_preserve_active_unknown_recent_and_shared(
    rig: dict[str, Any],
) -> None:
    expired, gone = await _evidence(rig, rig["a"], "expired", left="2028-03-01")
    recent, _ = await _evidence(rig, rig["a"], "recent", left="2028-03-02", visa_end="2031-01-01")
    active, _ = await _evidence(rig, rig["a"], "active", left="2020-01-01", status="active")
    unknown, _ = await _evidence(rig, rig["a"], "unknown", left=None)
    other, _ = await _evidence(rig, rig["b"], "foreign", left="2029-03-02")
    shared, shared_file = await _evidence(
        rig, rig["a"], "shared", left="2028-01-01", visa_end="2031-01-01"
    )
    ctx = {"owner_engine": rig["owner"], "storage": rig["app"].state.files.storage, "now": NOW}
    await retention_purge_daily(ctx)
    async with rig["owner"].connect() as c:
        for emp, expected in (
            (expired, 0),
            (recent, 2),
            (active, 2),
            (unknown, 2),
            (other, 2),
            (shared, 0),
        ):
            assert (
                await c.scalar(
                    text("select count(*) from rtw_checks where subject_id=:e"), {"e": emp}
                )
                == expected
            )
        assert (
            await c.scalar(
                text("select count(*) from sponsor_documents where employee_id=:e"), {"e": shared}
            )
            == 1
        )
        assert (
            await c.scalar(text("select count(*) from files where id=:f"), {"f": shared_file}) == 1
        )
        assert await c.scalar(text("select count(*) from files where id=:f"), {"f": gone}) == 0
        assert (
            await c.scalar(text("select count(*) from employees where id=:e"), {"e": expired}) == 1
        )
    async with AsyncSession(rig["owner"]) as db:
        events = (
            await db.scalars(
                select(AuditEvent).where(AuditEvent.action == "employee.retention_purged")
            )
        ).all()
        assert {event.entity_id for event in events} == {expired, shared}
        expired_events = [event for event in events if event.entity_id == expired]
        assert len(expired_events) == 1
        event = expired_events[0]
        assert event.company_id == rig["a"]
        assert event.actor_user_id is None
        assert event.actor_type == "system"
        assert event.entity_type == "employee"
        assert event.after == {"rtw_checks": 2, "rtw_documents": 1, "sponsor_documents": 1}
        assert event.reason == (
            "Retention: RTW evidence employment + 2 years / sponsor records + 1 year"
        )
        shared_event = next(event for event in events if event.entity_id == shared)
        assert shared_event.after == {"rtw_checks": 2, "rtw_documents": 1, "sponsor_documents": 0}
        event_ids = {event.id for event in events}
    assert await retention_purge_daily(ctx) == 0
    async with AsyncSession(rig["owner"]) as db:
        assert (
            set(
                await db.scalars(
                    select(AuditEvent.id).where(AuditEvent.action == "employee.retention_purged")
                )
            )
            == event_ids
        )
    assert anniversary(date(2028, 2, 29), 1) == date(2029, 2, 28)


async def test_retention_does_not_delete_storage_inside_the_transaction(
    rig: dict[str, Any],
) -> None:
    emp, file = await _evidence(rig, rig["a"], "retry", left="2020-01-01")

    class Down:
        async def delete(self, key: str) -> None:
            raise RuntimeError("storage unavailable")

    ctx = {"owner_engine": rig["owner"], "storage": Down(), "now": NOW}
    assert await retention_purge_daily(ctx) >= 4
    async with rig["owner"].connect() as c:
        assert (
            await c.scalar(text("select count(*) from rtw_checks where subject_id=:e"), {"e": emp})
            == 0
        )
        assert await c.scalar(text("select count(*) from files where id=:f"), {"f": file}) == 0
    assert await retention_purge_daily(ctx) == 0


async def test_missing_owner_is_an_observable_failure() -> None:
    with pytest.raises(RuntimeError, match="owner_engine"):
        await retention_purge_daily({})


async def test_recent_leavers_are_skipped_and_an_interrupted_run_resumes(
    rig: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """ISS-34: only possibly-due leavers are locked, in committed batches."""
    from app.jobs import retention

    first, _ = await _evidence(rig, rig["a"], "batch-1", left="2027-01-01")
    second, _ = await _evidence(rig, rig["a"], "batch-2", left="2027-01-02")
    recent, _ = await _evidence(rig, rig["a"], "batch-recent", left="2029-06-01")
    async with AsyncSession(rig["owner"]) as db:
        candidates = set(await db.scalars(retention._candidates(NOW.date())))
    assert {first, second} <= candidates
    assert recent not in candidates  # left under a year ago: never locked

    monkeypatch.setattr(retention, "BATCH", 1)
    real, calls = retention._purge_people, []

    async def interrupted(db: Any, storage: Any, now: Any, people: Any) -> int:
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("worker stopped")
        return await real(db, storage, now, people)

    monkeypatch.setattr(retention, "_purge_people", interrupted)
    ctx = {"owner_engine": rig["owner"], "storage": rig["app"].state.files.storage, "now": NOW}
    with pytest.raises(RuntimeError):
        await retention_purge_daily(ctx)

    async def checks(employee: uuid.UUID) -> int:
        async with rig["owner"].connect() as c:
            return int(
                await c.scalar(
                    text("select count(*) from rtw_checks where subject_id=:e"), {"e": employee}
                )
                or 0
            )

    done = [e for e in (first, second) if await checks(e) == 0]
    assert len(done) == 1  # the first batch was committed before the stop
    monkeypatch.setattr(retention, "_purge_people", real)
    await retention_purge_daily(ctx)
    assert await checks(first) == await checks(second) == 0
    assert await checks(recent) == 2
