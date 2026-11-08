"""T15.2: the rules-data importer writes a draft version from the saved GOV.UK pages, re-running it
adds nothing, a changed page gives a new draft with a reviewable diff, and publishing makes one
version live and sets the RQF levels. Tenants read the rules tables but cannot change them."""

from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt
import uuid
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import NullPool

from app.modules.soc_rules.engine import Applicant, CheckInput, RulesData, evaluate
from app.modules.soc_rules.importer import (
    ImportResult,
    RulesImportError,
    import_rules_source,
    publish_rules_version,
)
from app.modules.soc_rules.loader import NoRulesVersionError, load_rules_data
from app.modules.soc_rules.source import PAGE_KINDS, RulesSource, load_rules_source
from tests.db.support import engine_for, temporary_database

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tests.db.support import DatabaseUnderTest

RULES = Path(__file__).resolve().parents[3] / "data" / "raw" / "rules"
RULE_TABLES = (
    "going_rates",
    "pay_scale_rates",
    "ineligible_codes",
    "shortage_list_entries",
    "salary_rules",
)
# Unit groups to receive an RQF level at publish: Table 1, Table 1a, the RQF 2 exception in
# Table 1a's notes, Table 2a, and a code in no table.
UNIT_GROUPS = ("2134", "3544", "6135", "6116", "1112")


@pytest.fixture(scope="module")
def source() -> RulesSource:
    return load_rules_source(
        {
            kind: (
                RULES / f"appendix-{kind}-2026-10-29.html",
                RULES / f"appendix-{kind}-2026-10-29.json",
            )
            for kind in PAGE_KINDS
        }
    )


@pytest.fixture
def rules_database(stack: None) -> Iterator[DatabaseUnderTest]:
    with temporary_database() as db:
        yield db


def _changed(source: RulesSource) -> RulesSource:
    """The same pages with Table 1's 2134 going rate raised, bricklayers off the ISL, and a new
    hash for each page, as a GOV.UK update would bring."""
    going = tuple(
        dataclasses.replace(r, annual_rate=Decimal("56000"))
        if (r.table, r.soc_code) == ("1", "2134")
        else r
        for r in source.going_rates
    )
    shortage = tuple(r for r in source.shortage if (r.list_name, r.soc_code) != ("ISL", "5313"))
    pages = tuple(
        dataclasses.replace(p, sha256="0" * 63 + str(i)) for i, p in enumerate(source.pages)
    )
    return dataclasses.replace(source, going_rates=going, shortage=shortage, pages=pages)


async def _import(url: str, source: RulesSource) -> ImportResult:
    engine = engine_for(url, poolclass=NullPool, hide_parameters=True)
    try:
        async with AsyncSession(engine) as db:
            result = await import_rules_source(db, source)
            await db.commit()
        return result
    finally:
        await engine.dispose()


async def _publish(url: str, version_id: uuid.UUID) -> None:
    engine = engine_for(url, poolclass=NullPool, hide_parameters=True)
    try:
        async with AsyncSession(engine) as db:
            await publish_rules_version(db, version_id)
            await db.commit()
    finally:
        await engine.dispose()


async def _rows(url: str, sql: str, params: dict[str, Any] | None = None) -> list[Any]:
    engine = engine_for(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            return list((await connection.execute(text(sql), params or {})).all())
    finally:
        await engine.dispose()


def _scalar(url: str, sql: str, params: dict[str, Any] | None = None) -> Any:
    return asyncio.run(_rows(url, sql, params))[0][0]


async def _add_unit_groups(url: str) -> None:
    engine = engine_for(url, poolclass=NullPool)
    vector = "[" + ",".join(["0"] * 384) + "]"
    try:
        async with engine.begin() as connection:
            for code in UNIT_GROUPS:
                await connection.execute(
                    text(
                        "insert into soc_unit_groups (code, title, description, tasks, "
                        "entry_requirements, typical_titles, embedding) values "
                        "(:code, 'A group', 'Describes it.', '{}', '', '{}', :vector)"
                    ),
                    {"code": code, "vector": vector},
                )
    finally:
        await engine.dispose()


async def _execute_as_tenant(url: str, sql: str) -> int:
    engine = engine_for(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            return int((await connection.execute(text(sql))).rowcount)
    except DBAPIError:
        return 0
    finally:
        await engine.dispose()


def test_the_import_writes_one_draft_with_every_row(
    rules_database: DatabaseUnderTest, source: RulesSource
) -> None:
    result = asyncio.run(_import(rules_database.owner_url, source))
    url = rules_database.owner_url

    assert result.version_id is not None
    assert not result.unchanged
    assert result.counts == {
        "going_rates": len(source.going_rates),
        "pay_scale_rates": len(source.pay_scales),
        "ineligible_codes": len(source.ineligible),
        "shortage_list_entries": len(source.shortage),
        "salary_rules": 11,
    }
    assert result.diff_summary["against"] is None
    version = asyncio.run(
        _rows(
            url,
            "select status, effective_from, jsonb_array_length(source_urls) from rules_versions",
        )
    )
    assert [(v[0], str(v[1]), v[2]) for v in version] == [("draft", "2026-10-29", 3)]
    for table in RULE_TABLES:
        assert _scalar(url, f"select count(*) from {table}") == result.counts[table]  # noqa: S608
    rate = asyncio.run(
        _rows(
            url,
            "select annual_rate, rate_70, basis_hours from going_rates "
            "where \"table\" = '1' and soc_code = '2134'",
        )
    )
    assert rate == [(Decimal("54700.00"), Decimal("38300.00"), Decimal("37.5"))]


def test_dependants_follow_tables_1_2_and_3(
    rules_database: DatabaseUnderTest, source: RulesSource
) -> None:
    asyncio.run(_import(rules_database.owner_url, source))
    rows = asyncio.run(
        _rows(
            rules_database.owner_url,
            "select list, soc_code, dependants_allowed from shortage_list_entries",
        )
    )
    in_tables = {r.soc_code for r in source.going_rates if r.table in ("1", "2", "3")}

    assert {(r[0], r[1]): r[2] for r in rows} == {
        (r.list_name, r.soc_code): r.soc_code in in_tables for r in source.shortage
    }
    assert not any(r[2] for r in rows if r[0] == "TSL")  # every TSL code is an RQF 3-5 code


def test_the_same_pages_again_add_nothing(
    rules_database: DatabaseUnderTest, source: RulesSource
) -> None:
    asyncio.run(_import(rules_database.owner_url, source))
    again = asyncio.run(_import(rules_database.owner_url, source))

    assert again.unchanged
    assert again.version_id is None
    assert _scalar(rules_database.owner_url, "select count(*) from rules_versions") == 1
    assert _scalar(rules_database.owner_url, "select count(*) from salary_rules") == 11


def test_publish_makes_the_draft_live_and_sets_rqf_levels(
    rules_database: DatabaseUnderTest, source: RulesSource
) -> None:
    url = rules_database.owner_url
    asyncio.run(_add_unit_groups(url))
    result = asyncio.run(_import(url, source))
    assert result.version_id is not None

    asyncio.run(_publish(url, result.version_id))

    status = asyncio.run(_rows(url, "select status, published_at is not null from rules_versions"))
    assert status == [("live", True)]
    levels = dict(asyncio.run(_rows(url, "select code, rqf_level from soc_unit_groups")))
    assert levels == {"2134": "6", "3544": "3-5", "6135": "below", "6116": "below", "1112": None}
    with pytest.raises(RulesImportError, match="Only a draft"):
        asyncio.run(_publish(url, result.version_id))


def test_a_changed_page_gives_a_new_draft_with_a_diff_against_live(
    rules_database: DatabaseUnderTest, source: RulesSource
) -> None:
    url = rules_database.owner_url
    first = asyncio.run(_import(url, source))
    assert first.version_id is not None
    asyncio.run(_publish(url, first.version_id))

    second = asyncio.run(_import(url, _changed(source)))
    diff = second.diff_summary

    assert second.version_id is not None
    assert diff["against"]["id"] == str(first.version_id)
    assert diff["has_changes"]
    assert diff["sections"]["going_rates"]["changed"] == [
        {"key": "1|2134|", "field": "annual_rate", "from": "54700.00", "to": "56000.00"}
    ]
    assert diff["sections"]["shortage_list_entries"]["removed"] == ["ISL|5313"]
    assert diff["sections"]["salary_rules"] == {"added": [], "removed": [], "changed": []}
    # The live version is untouched until the new draft is published.
    statuses = sorted(r[0] for r in asyncio.run(_rows(url, "select status from rules_versions")))
    assert statuses == ["draft", "live"]
    live_rate = _scalar(
        url,
        "select g.annual_rate from going_rates g join rules_versions v on v.id = g.rules_version_id "
        "where v.status = 'live' and g.\"table\" = '1' and g.soc_code = '2134'",
    )
    assert live_rate == Decimal("54700.00")

    # A newer import replaces the waiting draft rather than piling up drafts.
    third_source = dataclasses.replace(
        _changed(source),
        pages=tuple(dataclasses.replace(p, sha256="f" * 64) for p in source.pages),
    )
    asyncio.run(_import(url, third_source))
    assert _scalar(url, "select count(*) from rules_versions where status = 'draft'") == 1

    draft = _scalar(url, "select id from rules_versions where status = 'draft'")
    asyncio.run(_publish(url, draft))
    statuses = sorted(r[0] for r in asyncio.run(_rows(url, "select status from rules_versions")))
    assert statuses == ["live", "retired"]


def test_tenants_can_read_the_rules_tables_but_not_change_them(
    rules_database: DatabaseUnderTest, source: RulesSource
) -> None:
    asyncio.run(_import(rules_database.owner_url, source))

    for table in ("rules_versions", *RULE_TABLES):
        changed = asyncio.run(_execute_as_tenant(rules_database.app_url, f"delete from {table}"))  # noqa: S608
        assert changed == 0, table
        assert _scalar(rules_database.app_url, f"select count(*) from {table}") > 0, table  # noqa: S608


async def _load(url: str, version_id: uuid.UUID | None = None) -> RulesData:
    engine = engine_for(url, poolclass=NullPool)
    try:
        async with AsyncSession(engine) as db:
            return await load_rules_data(db, version_id)
    finally:
        await engine.dispose()


def test_t15_3_the_engine_gives_the_same_answer_on_the_stored_version(
    rules_database: DatabaseUnderTest, source: RulesSource
) -> None:
    url = rules_database.owner_url
    with pytest.raises(NoRulesVersionError):
        asyncio.run(_load(url))
    result = asyncio.run(_import(url, source))
    assert result.version_id is not None
    draft = asyncio.run(_load(url, result.version_id))
    asyncio.run(_publish(url, result.version_id))

    # Tenants read the live version (the checker runs as app_user).
    live = asyncio.run(_load(rules_database.app_url))
    parsed = RulesData.from_source(source)

    assert live.version_id == str(result.version_id) == draft.version_id
    assert live.effective_from == parsed.effective_from
    assert sorted(live.going_rates, key=repr) == sorted(parsed.going_rates, key=repr)
    assert sorted(live.pay_scales, key=repr) == sorted(parsed.pay_scales, key=repr)
    assert sorted(live.shortage, key=repr) == sorted(parsed.shortage, key=repr)
    assert live.salary_rules == parsed.salary_rules
    assert live.table_notes == parsed.table_notes
    check = CheckInput(
        soc_code="2134",
        weekly_hours=Decimal("37.5"),
        offered_salary=Decimal("38300"),
        salary_per="year",
        work_nation="England",
        cos_assignment_date=dt.date(2026, 11, 15),
        applicant=Applicant(under_26=True),
    )
    stored, fresh = evaluate(live, check), evaluate(parsed, check)
    assert stored.options == fresh.options
    assert stored.verdict == fresh.verdict
    assert stored.rules_version_id == str(result.version_id)
