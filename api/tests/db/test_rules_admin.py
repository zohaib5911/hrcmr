"""T15.7: platform admins see, publish and roll back the SOC rules versions. Only a platform admin can
(a company administrator gets 403), every change is audited, and a saved check keeps the version it
was made with.

The rig's clean-up truncates the rules (their rows refer to users), so the saved rules are published
again for every test, after it. A draft is made by importing the same pages with a different hash."""

from __future__ import annotations

import asyncio
import dataclasses
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import NullPool

from app.modules.soc_rules.importer import import_rules_source, publish_rules_version
from app.modules.soc_rules.source import PAGE_KINDS, RulesSource, load_rules_source
from tests.db.support import DatabaseUnderTest, engine_for, temporary_database
from tests.db.test_employee_documents import rig as rig
from tests.db.test_soc_match import _load_sample

API = "/api/v1"
RULES = Path(__file__).resolve().parents[3] / "data" / "raw" / "rules"


def _source() -> RulesSource:
    return load_rules_source(
        {
            kind: (
                RULES / f"appendix-{kind}-2026-10-29.html",
                RULES / f"appendix-{kind}-2026-10-29.json",
            )
            for kind in PAGE_KINDS
        }
    )


async def _import(url: str, source: RulesSource, publish: bool) -> str:
    engine = engine_for(url, poolclass=NullPool, hide_parameters=True)
    try:
        async with AsyncSession(engine) as db:
            result = await import_rules_source(db, source)
            assert result.version_id is not None
            if publish:
                await publish_rules_version(db, result.version_id)
            await db.commit()
            return str(result.version_id)
    finally:
        await engine.dispose()


async def _audit_actions(url: str) -> list[str]:
    engine = engine_for(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(
                text(
                    "select action from audit_events where action like 'platform.rules%' "
                    "order by created_at"
                )
            )
            return [str(row[0]) for row in rows.all()]
    finally:
        await engine.dispose()


@pytest.fixture(scope="module")
def database(stack: None) -> Iterator[DatabaseUnderTest]:
    with temporary_database() as db:
        asyncio.run(_load_sample(db.owner_url))
        yield db


@pytest.fixture(autouse=True)
async def ready(rig: dict[str, Any], database: DatabaseUnderTest) -> None:
    await _import(database.owner_url, _source(), publish=True)


async def _as_platform_admin(rig: dict[str, Any], admin: Any) -> None:
    """Gives the signed-in administrator platform access with MFA, as the learning tests do."""
    platform_id = next(
        u["user_id"] for u in (await admin.get(f"{API}/users")).json()["users"] if u["is_you"]
    )
    async with rig["owner"].begin() as c:
        await c.execute(
            text("insert into platform_admins (user_id,level) values (:u,'support')"),
            {"u": platform_id},
        )
        await c.execute(text("update users set mfa_enabled=true where id=:u"), {"u": platform_id})


async def _draft(database: DatabaseUnderTest) -> str:
    """A draft from the same tables with changed page hashes, so it differs from the live version."""
    source = _source()
    changed = dataclasses.replace(
        source, pages=tuple(dataclasses.replace(page, sha256="0" * 64) for page in source.pages)
    )
    return await _import(database.owner_url, changed, publish=False)


async def test_only_a_platform_admin_sees_or_publishes_the_rules(rig: dict[str, Any]) -> None:
    company_admin = await rig["person"]("company_admin", rig["a"])
    assert (await company_admin.get(f"{API}/platform/rules")).status_code == 403
    refused = await company_admin.post(
        f"{API}/platform/rules/00000000-0000-0000-0000-000000000000/publish"
    )
    assert refused.status_code == 403


async def test_a_platform_admin_publishes_a_draft_and_rolls_back(
    rig: dict[str, Any], database: DatabaseUnderTest
) -> None:
    admin = await rig["person"]("company_admin", rig["a"])
    await _as_platform_admin(rig, admin)
    live_id = (await admin.get(f"{API}/platform/rules")).json()["items"][0]["id"]
    draft_id = await _draft(database)

    listed = (await admin.get(f"{API}/platform/rules")).json()["items"]
    assert {item["id"]: item["status"] for item in listed} == {live_id: "live", draft_id: "draft"}

    published = await admin.post(f"{API}/platform/rules/{draft_id}/publish")
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "live"
    again = await admin.post(f"{API}/platform/rules/{draft_id}/publish")
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "NOT_A_DRAFT"

    rolled = await admin.post(f"{API}/platform/rules/{live_id}/rollback")
    assert rolled.status_code == 200, rolled.text
    assert rolled.json()["status"] == "live"
    not_retired = await admin.post(f"{API}/platform/rules/{live_id}/rollback")
    assert not_retired.status_code == 409
    assert not_retired.json()["error"]["code"] == "NOT_RETIRED"

    assert await _audit_actions(database.owner_url) == [
        "platform.rules_published",
        "platform.rules_rolled_back",
    ]


async def test_a_saved_check_keeps_the_rules_version_it_was_made_with(
    rig: dict[str, Any], database: DatabaseUnderTest
) -> None:
    recruiter = await rig["person"]("recruiter", rig["a"])
    body = {
        "job_title": "Adviser, sales",
        "soc_code": "7111",
        "check": {
            "weekly_hours": "37.5",
            "offered_salary": "30000.00",
            "salary_per": "year",
            "work_nation": "England",
            "cos_assignment_date": "2026-11-01",
            "applicant": {"situation": "outside_uk"},
        },
    }
    made = await recruiter.post(f"{API}/soc/checks", json=body)
    assert made.status_code == 200, made.text
    before = made.json()

    admin = await rig["person"]("company_admin", rig["a"])
    await _as_platform_admin(rig, admin)
    draft_id = await _draft(database)
    assert (await admin.post(f"{API}/platform/rules/{draft_id}/publish")).status_code == 200

    after = (await recruiter.get(f"{API}/soc/checks/{before['id']}")).json()
    assert after["result"]["rules_version_id"] == before["result"]["rules_version_id"]
    assert json.dumps(after["result"], sort_keys=True) == json.dumps(
        before["result"], sort_keys=True
    )
