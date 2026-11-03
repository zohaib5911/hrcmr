"""T8.1: verified seeds, scoped type CRUD/settings, validation and atomic audit."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from app.core.rbac_matrix import ROLES, scope_for
from app.db.session import TenantSession
from app.modules.leave.service import seed_types
from tests.db.support import DatabaseUnderTest, engine_for
from tests.db.test_compliance_hub import rig as rig

API = "/api/v1/leave"


@pytest.fixture
async def seeded(rig: dict[str, Any], database: DatabaseUnderTest) -> AsyncIterator[dict[str, Any]]:
    engine = engine_for(database.app_url, poolclass=NullPool)
    try:
        for company in (rig["a"], rig["b"]):
            async with TenantSession(engine, company_id=company) as db:
                await seed_types(db, company)
                await db.commit()
        yield rig
    finally:
        await engine.dispose()


async def test_twelve_defaults_have_sources_and_null_is_not_a_zero_allowance(
    seeded: dict[str, Any],
) -> None:
    admin = await seeded["person"]("company_admin", seeded["a"])
    response = await admin.get(API + "/types")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 12
    assert len({row["seed_key"] for row in rows}) == 12
    assert all(
        row["source_url"].startswith("https://www.gov.uk/") and row["checked_on"] == "2026-11-03"
        for row in rows
    )
    annual = next(row for row in rows if row["seed_key"] == "annual")
    assert (
        annual["days_per_year"],
        annual["carry_over_limit_days"],
        annual["counts_toward_statutory"],
    ) == ("28.00", "5.00", True)
    assert all(row["days_per_year"] is None for row in rows if row["seed_key"] != "annual")
    assert {row["seed_key"] for row in rows if not row["is_paid"]} == {
        "parental",
        "carer",
        "dependants",
        "unpaid",
    }
    assert "first full day" in next(row["rule_text"] for row in rows if row["seed_key"] == "sick")
    assert (await admin.get(API + "/settings")).json() == {
        "leave_year_start_month_day": "01-01",
        "allow_negative_leave_balance": False,
    }


async def test_types_are_edited_archived_and_retained_without_touching_other_companies(
    seeded: dict[str, Any],
) -> None:
    admin = await seeded["person"]("company_admin", seeded["a"])
    other = await seeded["person"]("company_admin", seeded["b"])
    payload = {
        "name": "  Study Leave  ",
        "is_paid": True,
        "days_per_year": "3.50",
        "carry_over_limit_days": "1.25",
        "accrual_method": "monthly",
        "colour": "green",
        "requires_approval": False,
    }
    made = await admin.post(API + "/types", json=payload)
    assert made.status_code == 201, made.text
    row = made.json()
    assert row["name"] == "Study Leave"
    assert row["source_url"] is row["checked_on"] is row["seed_key"] is None
    path = API + "/types/" + row["id"]
    assert (await admin.get(path)).json() == row
    duplicate = await admin.post(API + "/types", json={"name": "study leave"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["field"] == "name"
    foreign = (await other.get(API + "/types")).json()[0]["id"]
    for ident in (foreign, str(uuid.uuid4())):
        target = API + "/types/" + ident
        assert (await admin.get(target)).status_code == 404
        assert (await admin.patch(target, json={"name": "Stolen"})).status_code == 404
        assert (await admin.delete(target)).status_code == 404
    updated = await admin.patch(path, json={"name": "Professional Study", "days_per_year": None})
    assert updated.status_code == 200
    assert updated.json()["days_per_year"] is None
    assert updated.json()["carry_over_limit_days"] == "1.25"
    assert (await admin.delete(path)).status_code == 204
    assert (await admin.get(path)).status_code == 404
    assert (await admin.patch(path, json={"name": "Back"})).status_code == 404
    assert len((await admin.get(API + "/types")).json()) == 12
    retained = (await admin.get(API + "/types", params={"include_archived": True})).json()
    assert len(retained) == 13
    assert next(r for r in retained if r["id"] == row["id"])["archived_at"] is not None
    assert len((await other.get(API + "/types")).json()) == 12
    async with seeded["owner"].connect() as c:
        events = (
            await c.execute(
                text(
                    "select action,before,after from audit_events where entity_id=:i order by created_at,id"
                ),
                {"i": uuid.UUID(row["id"])},
            )
        ).all()
    assert [e[0] for e in events] == [
        "leave.type_created",
        "leave.type_updated",
        "leave.type_archived",
    ]
    assert events[1][1]["name"] == "Study Leave"
    assert events[1][2]["name"] == "Professional Study"


@pytest.mark.parametrize("role", ROLES)
async def test_leave_configuration_permissions_match_matrix(
    seeded: dict[str, Any], role: str
) -> None:
    person = await seeded["person"](role, seeded["a"])
    assert (await person.get(API + "/types")).status_code == (
        200 if scope_for(role, "leave.type.read") else 403
    )
    assert (await person.get(API + "/settings")).status_code == (
        200 if scope_for(role, "leave.config.read") else 403
    )
    assert (await person.post(API + "/types", json={"name": role})).status_code == (
        201 if scope_for(role, "leave.type.write") else 403
    )
    assert (
        await person.patch(API + "/settings", json={"leave_year_start_month_day": "04-06"})
    ).status_code == (200 if scope_for(role, "leave.config.write") else 403)


async def test_settings_patch_validates_real_recurring_dates_and_audits_only_changes(
    seeded: dict[str, Any],
) -> None:
    admin = await seeded["person"]("company_admin", seeded["a"])
    for value in ("02-29", "02-30", "04-31", "00-01", "13-01", "1-1", None):
        result = await admin.patch(API + "/settings", json={"leave_year_start_month_day": value})
        assert result.status_code == 422, value
    assert (
        await admin.patch(API + "/settings", json={"allow_negative_leave_balance": None})
    ).status_code == 422
    assert (await admin.patch(API + "/settings", json={"extra": True})).status_code == 422
    assert (
        await admin.patch(API + "/settings", json={"leave_year_start_month_day": "04-06"})
    ).json() == {"leave_year_start_month_day": "04-06", "allow_negative_leave_balance": False}
    assert (
        await admin.patch(API + "/settings", json={"allow_negative_leave_balance": True})
    ).json()["allow_negative_leave_balance"] is True
    await admin.patch(API + "/settings", json={"allow_negative_leave_balance": True})
    other = await seeded["person"]("company_admin", seeded["b"])
    assert (await other.get(API + "/settings")).json() == {
        "leave_year_start_month_day": "01-01",
        "allow_negative_leave_balance": False,
    }
    async with seeded["owner"].connect() as c:
        assert (
            await c.execute(
                text(
                    "select count(*) from audit_events where company_id=:c and action='leave.settings_updated'"
                ),
                {"c": seeded["a"]},
            )
        ).scalar_one() == 2


async def test_bad_type_input_is_refused_and_seed_provenance_is_read_only(
    seeded: dict[str, Any],
) -> None:
    admin = await seeded["person"]("company_admin", seeded["a"])
    target = API + "/types/" + (await admin.get(API + "/types")).json()[0]["id"]
    for patch in (
        {"name": "   "},
        {"name": None},
        {"is_paid": None},
        {"days_per_year": "-1"},
        {"carry_over_limit_days": "-0.5"},
        {"days_per_year": "1.001"},
        {"colour": "purple"},
        {"accrual_method": "daily"},
        {"seed_key": "custom"},
        {"source_url": "https://evil.example"},
        {"checked_on": "2027-01-01"},
    ):
        assert (await admin.patch(target, json=patch)).status_code == 422, patch
    assert (await admin.patch(target, json={"name": "Sick Leave"})).status_code == 409
    updated = await admin.patch(target, json={"name": "Annual holiday", "days_per_year": "30"})
    assert updated.status_code == 200
    assert updated.json()["checked_on"] == "2026-11-03"
    assert updated.json()["seed_key"] == "annual"
