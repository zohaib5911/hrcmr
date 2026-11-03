"""T8.2 durable balances: isolation, immutable history, concurrency and reconciliation."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.pool import NullPool

from app.core.errors import AppError, ConflictError, NotFoundError
from app.db.session import TenantSession
from app.modules.leave.ledger import balance, move, reconcile
from app.modules.leave.models import LeaveLedger
from app.modules.leave.service import seed_types
from tests.db.api_support import two_companies
from tests.db.support import DatabaseUnderTest, engine_for

YEAR = date(2026, 1, 1)


@pytest.fixture
async def ledger(database: DatabaseUnderTest) -> AsyncIterator[dict[str, Any]]:
    a, b = await two_companies(database)
    owner = engine_for(database.owner_url, poolclass=NullPool)
    app = engine_for(database.app_url, poolclass=NullPool)
    people = [uuid.uuid4(), uuid.uuid4()]
    async with owner.begin() as c:
        for company, person in zip((a, b), people, strict=True):
            await c.execute(
                text(
                    "insert into employees (id,company_id,employee_number,first_name,last_name,email,hire_date) values (:i,:c,'E1','Amira','Test','a@example.com','2026-01-01')"
                ),
                {"i": person, "c": company},
            )
            await c.execute(
                text(
                    "insert into working_pattern_days (company_id,weekday,is_working,hours) select :c,d,d<=5,case when d<=5 then 8 else 0 end from generate_series(1,7) d"
                ),
                {"c": company},
            )
        # Calendar fixture: two official-region dates plus a different region, all with fixed year.
        await c.execute(text("delete from bank_holidays"))
        await c.execute(
            text(
                "insert into bank_holidays (region,on_date,title,source) values ('england-and-wales','2026-01-01','New Year','https://www.gov.uk/bank-holidays'),('england-and-wales','2026-04-03','Good Friday','https://www.gov.uk/bank-holidays'),('scotland','2026-01-02','Scotland only','https://www.gov.uk/bank-holidays')"
            )
        )
    kinds = []
    for company in (a, b):
        async with TenantSession(app, company_id=company) as db:
            await seed_types(db, company)
            kinds.append(
                (
                    await db.execute(text("select id from leave_types where seed_key='annual'"))
                ).scalar_one()
            )
            await db.commit()
    try:
        yield {
            "app": app,
            "owner": owner,
            "a": a,
            "b": b,
            "employee": people[0],
            "foreign_employee": people[1],
            "type": kinds[0],
            "foreign_type": kinds[1],
        }
    finally:
        await app.dispose()
        await owner.dispose()


async def change(
    rig: dict[str, Any], operation: str, days: str, *, key: uuid.UUID | None = None
) -> uuid.UUID:
    async with TenantSession(rig["app"], company_id=rig["a"]) as db:
        if operation == "deduct":
            row = await move(
                db,
                rig["employee"],
                rig["type"],
                YEAR,
                operation="deduct",
                days=Decimal(days),
                reason="Reviewed correction",
                key=key or uuid.uuid4(),
            )
        elif operation == "set":
            row = await move(
                db,
                rig["employee"],
                rig["type"],
                YEAR,
                operation="set",
                days=Decimal(days),
                reason="Reviewed correction",
                key=key or uuid.uuid4(),
            )
        else:
            row = await move(
                db,
                rig["employee"],
                rig["type"],
                YEAR,
                operation="grant",
                days=Decimal(days),
                reason="Reviewed correction",
                key=key or uuid.uuid4(),
            )
        assert row is not None
        await db.commit()
        return row.id


async def current(rig: dict[str, Any]) -> Decimal:
    async with TenantSession(rig["app"], company_id=rig["a"]) as db:
        return await balance(db, rig["employee"], rig["type"], YEAR)


async def test_manual_grant_deduct_set_and_replay_after_later_changes(
    ledger: dict[str, Any],
) -> None:
    assert await current(ledger) == 0
    await change(ledger, "grant", "28")
    await change(ledger, "deduct", "3.50")
    key = uuid.uuid4()
    ident = await change(ledger, "set", "20", key=key)
    await change(ledger, "deduct", "1")
    assert await change(ledger, "set", "20", key=key) == ident
    assert await current(ledger) == Decimal(19)
    with pytest.raises(ConflictError, match="different change"):
        await change(ledger, "set", "21", key=key)
    # A zero-delta set still records its key and cannot later change the balance on replay.
    noop = uuid.uuid4()
    await change(ledger, "set", "19", key=noop)
    await change(ledger, "grant", "1")
    await change(ledger, "set", "19", key=noop)
    assert await current(ledger) == 20
    async with ledger["owner"].connect() as c:
        movements = (
            await c.execute(text("select entry_type,days from leave_ledger order by created_at,id"))
        ).all()
    assert movements == [
        ("grant", Decimal(28)),
        ("deduct", Decimal("-3.5")),
        ("set", Decimal("-4.5")),
        ("deduct", Decimal(-1)),
        ("set", Decimal(0)),
        ("grant", Decimal(1)),
    ]


@pytest.mark.parametrize("value", ["0", "-1", "0.001", "NaN", "Infinity", "1000000"])
async def test_invalid_manual_grants(ledger: dict[str, Any], value: str) -> None:
    with pytest.raises(AppError, match="valid day amount"):
        await change(ledger, "grant", value)
    assert await current(ledger) == 0


async def test_negative_policy_and_transaction_rollback(ledger: dict[str, Any]) -> None:
    with pytest.raises(ConflictError, match="negative"):
        await change(ledger, "deduct", "1")
    async with ledger["owner"].begin() as c:
        await c.execute(
            text("update companies set allow_negative_leave_balance=true where id=:c"),
            {"c": ledger["a"]},
        )
    await change(ledger, "set", "-2")
    assert await current(ledger) == -2
    async with TenantSession(ledger["app"], company_id=ledger["a"]) as db:
        await move(
            db,
            ledger["employee"],
            ledger["type"],
            YEAR,
            operation="grant",
            days=Decimal(10),
            reason="Will roll back",
            key=uuid.uuid4(),
        )
        await db.rollback()
    assert await current(ledger) == -2


async def test_concurrent_grants_retries_and_deductions_serialize(ledger: dict[str, Any]) -> None:
    key = uuid.uuid4()
    ids = await asyncio.gather(*(change(ledger, "grant", "5", key=key) for _ in range(3)))
    assert len(set(ids)) == 1
    outcomes = await asyncio.gather(
        *(change(ledger, "deduct", "4") for _ in range(2)), return_exceptions=True
    )
    assert sum(isinstance(o, ConflictError) for o in outcomes) == 1
    assert await current(ledger) == 1


async def test_reconciliation_is_idempotent_and_preserves_manual_movements(
    ledger: dict[str, Any],
) -> None:
    async with TenantSession(ledger["app"], company_id=ledger["a"]) as db:
        calc, entries = await reconcile(db, ledger["employee"], ledger["type"], YEAR)
        assert (calc.entitlement, calc.calendar_days, calc.standard_day_hours) == (
            Decimal(28),
            Decimal(2),
            Decimal(8),
        )
        assert [e.days for e in entries] == [28, -2]
        await db.commit()
        assert (await reconcile(db, ledger["employee"], ledger["type"], YEAR))[1] == []
        await db.commit()
    await change(ledger, "grant", "3")
    async with ledger["owner"].begin() as c:
        await c.execute(
            text(
                "insert into employee_assignments (company_id,employee_id,employment_type,custom_working_days,hours_per_day,effective_from) values (:c,:e,'part_time','[\"mon\",\"tue\",\"wed\"]',8,'2026-01-01')"
            ),
            {"c": ledger["a"], "e": ledger["employee"]},
        )
    async with TenantSession(ledger["app"], company_id=ledger["a"]) as db:
        calc, entries = await reconcile(db, ledger["employee"], ledger["type"], YEAR)
        assert (calc.entitlement, calc.calendar_days) == (Decimal("16.8"), Decimal(0))
        assert [e.days for e in entries] == [Decimal("-11.2"), 2]
        await db.commit()
    assert await current(ledger) == Decimal("19.8")


async def test_closures_deduplicate_bank_days_and_archive_refunds(ledger: dict[str, Any]) -> None:
    async with ledger["owner"].begin() as c:
        await c.execute(
            text(
                "insert into company_holidays (company_id,name,start_date,end_date,deduct_from_annual_leave) values (:c,'Shutdown','2026-01-01','2026-01-04',true),(:c,'Overlap','2026-01-02','2026-01-03',true),(:c,'Free','2026-01-05','2026-01-05',false)"
            ),
            {"c": ledger["a"]},
        )
    async with TenantSession(ledger["app"], company_id=ledger["a"]) as db:
        calc, _ = await reconcile(db, ledger["employee"], ledger["type"], YEAR)
        assert calc.calendar_days == 3  # Jan 1, Jan 2, Good Friday
        await db.commit()
    async with ledger["owner"].begin() as c:
        await c.execute(
            text("update company_holidays set archived_at=now() where company_id=:c"),
            {"c": ledger["a"]},
        )
    async with TenantSession(ledger["app"], company_id=ledger["a"]) as db:
        _, entries = await reconcile(db, ledger["employee"], ledger["type"], YEAR)
        assert [e.days for e in entries] == [1]
        await db.commit()


async def test_missing_region_coverage_fails_without_partial_grant(ledger: dict[str, Any]) -> None:
    async with TenantSession(ledger["app"], company_id=ledger["a"]) as db:
        with pytest.raises(AppError, match="does not cover"):
            await reconcile(db, ledger["employee"], ledger["type"], date(2027, 1, 1))
        await db.commit()
        assert (await db.execute(select(LeaveLedger))).scalars().all() == []


async def test_view_and_foreign_references_enforce_tenant_boundary(ledger: dict[str, Any]) -> None:
    await change(ledger, "grant", "28")
    async with TenantSession(ledger["app"], company_id=ledger["b"]) as db:
        assert (await db.execute(text("select * from leave_balances"))).all() == []
        assert await balance(db, ledger["employee"], ledger["type"], YEAR) == 0
    for person, kind in (
        (ledger["foreign_employee"], ledger["type"]),
        (ledger["employee"], ledger["foreign_type"]),
    ):
        async with TenantSession(ledger["app"], company_id=ledger["a"]) as db:
            with pytest.raises(NotFoundError):
                await move(
                    db,
                    person,
                    kind,
                    YEAR,
                    operation="grant",
                    days=Decimal(1),
                    reason="Cross tenant",
                    key=uuid.uuid4(),
                )
        # Even raw SQL cannot attach a tenant A movement to tenant B parents.
        async with ledger["owner"].begin() as c:
            with pytest.raises(IntegrityError):
                await c.execute(
                    text(
                        "insert into leave_ledger (company_id,employee_id,leave_type_id,leave_year_start,entry_type,days,reason) values (:c,:e,:t,'2026-01-01','grant',1,'Invalid')"
                    ),
                    {"c": ledger["a"], "e": person, "t": kind},
                )


@pytest.mark.parametrize("sql", ["update leave_ledger set days=100", "delete from leave_ledger"])
async def test_ledger_history_cannot_be_changed_even_by_owner(
    ledger: dict[str, Any], sql: str
) -> None:
    await change(ledger, "grant", "28")
    async with ledger["owner"].begin() as c:
        with pytest.raises(DBAPIError, match="append-only"):
            await c.execute(text(sql))
    assert await current(ledger) == 28


async def test_monthly_accrual_null_allowance_and_year_isolation(ledger: dict[str, Any]) -> None:
    async with ledger["owner"].begin() as c:
        await c.execute(
            text(
                "update leave_types set accrual_method='monthly',bank_holidays_included=false where id=:t"
            ),
            {"t": ledger["type"]},
        )
    async with TenantSession(ledger["app"], company_id=ledger["a"]) as db:
        calc, _ = await reconcile(db, ledger["employee"], ledger["type"], date(2026, 3, 31))
        assert calc.entitlement == 7
        await db.commit()
        calc, entries = await reconcile(db, ledger["employee"], ledger["type"], date(2026, 4, 30))
        assert calc.entitlement == Decimal("9.34")
        assert [(e.entry_type, e.days) for e in entries] == [("accrual", Decimal("2.34"))]
        await db.commit()
        assert await balance(db, ledger["employee"], ledger["type"], date(2025, 1, 1)) == 0
        sick = (
            await db.execute(text("select id from leave_types where seed_key='sick'"))
        ).scalar_one()
        calc, entries = await reconcile(db, ledger["employee"], sick, YEAR)
        assert calc.entitlement is None
        assert entries == []
        assert await balance(db, ledger["employee"], sick, YEAR) == 0


async def test_all_movement_types_sum_in_view_and_created_by_is_stamped(
    ledger: dict[str, Any],
) -> None:
    actor = uuid.uuid4()
    movements = [
        ("grant", "28"),
        ("accrual", "1.25"),
        ("carry_over", "5"),
        ("taken", "-2.5"),
        ("adjustment", "-.25"),
        ("deduct", "-1"),
        ("set", "3"),
        ("year_end_expiry", "-2"),
    ]
    async with TenantSession(ledger["app"], company_id=ledger["a"], user_id=actor) as db:
        for kind, days in movements:
            db.add(
                LeaveLedger(
                    company_id=ledger["a"],
                    employee_id=ledger["employee"],
                    leave_type_id=ledger["type"],
                    leave_year_start=YEAR,
                    entry_type=kind,
                    days=Decimal(days),
                    reason="Test movement",
                )
            )
        await db.commit()
        assert await balance(db, ledger["employee"], ledger["type"], YEAR) == Decimal("31.5")
        assert (await db.execute(text("select days from leave_balances"))).scalar_one() == Decimal(
            "31.5"
        )
        assert set((await db.execute(select(LeaveLedger.created_by))).scalars()) == {actor}


async def test_bank_inclusion_switch_and_irregular_hours_are_explicit(
    ledger: dict[str, Any],
) -> None:
    async with ledger["owner"].begin() as c:
        await c.execute(
            text("update companies set bank_holidays_non_working=false where id=:c"),
            {"c": ledger["a"]},
        )
    async with TenantSession(ledger["app"], company_id=ledger["a"]) as db:
        calc, _ = await reconcile(db, ledger["employee"], ledger["type"], YEAR)
        assert calc.calendar_days == 0
        await db.commit()
    async with ledger["owner"].begin() as c:
        await c.execute(
            text(
                "insert into employee_assignments (company_id,employee_id,employment_type,effective_from) values (:c,:e,'zero_hours','2026-01-01')"
            ),
            {"c": ledger["a"], "e": ledger["employee"]},
        )
    async with TenantSession(ledger["app"], company_id=ledger["a"]) as db:
        with pytest.raises(AppError, match="irregular hours"):
            await reconcile(db, ledger["employee"], ledger["type"], YEAR)
    # A reviewed manual grant remains available without guessing hours worked.
    await change(ledger, "grant", "1")


async def test_bad_year_reason_and_changed_idempotency_payload(ledger: dict[str, Any]) -> None:
    key = uuid.uuid4()
    await change(ledger, "grant", "5", key=key)
    with pytest.raises(ConflictError, match="different change"):
        await change(ledger, "grant", "6", key=key)
    async with TenantSession(ledger["app"], company_id=ledger["a"]) as db:
        for year, reason, message in [
            (YEAR, " ", "reason"),
            (date(2026, 2, 1), "Reviewed", "configured leave year"),
        ]:
            with pytest.raises(AppError, match=message):
                await move(
                    db,
                    ledger["employee"],
                    ledger["type"],
                    year,
                    operation="grant",
                    days=Decimal(1),
                    reason=reason,
                    key=uuid.uuid4(),
                )
    assert await current(ledger) == 5


async def test_personal_days_inherit_actual_company_hours_when_no_hours_override(
    ledger: dict[str, Any],
) -> None:
    async with ledger["owner"].begin() as c:
        await c.execute(
            text("update working_pattern_days set hours=4 where company_id=:c and weekday=5"),
            {"c": ledger["a"]},
        )
        await c.execute(
            text(
                "insert into employee_assignments (company_id,employee_id,employment_type,custom_working_days,effective_from) values (:c,:e,'part_time','[\"mon\",\"tue\",\"wed\"]','2026-01-01')"
            ),
            {"c": ledger["a"], "e": ledger["employee"]},
        )
    async with TenantSession(ledger["app"], company_id=ledger["a"]) as db:
        calc, _ = await reconcile(db, ledger["employee"], ledger["type"], YEAR)
        assert calc.standard_day_hours == Decimal("7.2")
        assert calc.entitlement == Decimal("18.67")  # 28 * 24 / 36, rounded up once
        assert calc.calendar_days == 0
