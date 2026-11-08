"""T15.1: the SOC importer is re-runnable with no duplicates, updates changed rows in place, keeps the
rules-owned rqf level, stores 384-dimension embeddings, and tenants can read the reference tables but
not change them. The embedder is a fake, so these tests never download a model."""

from __future__ import annotations

import asyncio
import dataclasses
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import NullPool

from app.modules.soc.importer import ImportCounts, load_soc_source
from app.modules.soc.source import SocSource, load_source
from tests.db.support import engine_for, temporary_database

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from tests.db.support import DatabaseUnderTest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "soc"


def _fake_embed(texts: Sequence[str]) -> list[list[float]]:
    return [[float((len(text) * (dim + 1)) % 13) for dim in range(384)] for text in texts]


@pytest.fixture(scope="module")
def soc_database(stack: None) -> Iterator[DatabaseUnderTest]:
    with temporary_database() as db:
        yield db


def _source() -> SocSource:
    return load_source(
        FIXTURES / "soc2020-coding-index-sample.xlsx",
        FIXTURES / "soc2020-unit-groups-sample.xlsx",
    )


async def _import(url: str, source: SocSource) -> ImportCounts:
    engine = engine_for(url, poolclass=NullPool, hide_parameters=True)
    try:
        async with AsyncSession(engine) as db:
            counts = await load_soc_source(db, source, _fake_embed)
            await db.commit()
        return counts
    finally:
        await engine.dispose()


async def _scalar(url: str, sql: str, params: dict[str, Any] | None = None) -> Any:
    engine = engine_for(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            return (await connection.execute(text(sql), params or {})).scalar_one()
    finally:
        await engine.dispose()


async def _run(url: str, sql: str, params: dict[str, Any]) -> None:
    """A committed write, as the owner would make it (the owner may change reference rows)."""
    engine = engine_for(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(sql), params)
    finally:
        await engine.dispose()


async def _execute_as_tenant(url: str, sql: str) -> int:
    """Runs a write as the app role. Returns the rows it changed, or 0 when the database refuses."""
    engine = engine_for(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            result = await connection.execute(text(sql))
            return int(result.rowcount)
    except DBAPIError:
        return 0
    finally:
        await engine.dispose()


def test_the_import_is_re_runnable_with_no_duplicates(soc_database: DatabaseUnderTest) -> None:
    first = asyncio.run(_import(soc_database.owner_url, _source()))
    second = asyncio.run(_import(soc_database.owner_url, _source()))

    assert first.unit_groups == second.unit_groups == 9
    assert first.index_entries == second.index_entries == 36
    assert first.cross_references_skipped == second.cross_references_skipped == 3
    assert second.unit_groups_in_table == 9
    assert second.index_entries_in_table == 36


def test_every_row_has_a_384_dimension_embedding(soc_database: DatabaseUnderTest) -> None:
    asyncio.run(_import(soc_database.owner_url, _source()))

    dims = asyncio.run(
        _scalar(
            soc_database.owner_url,
            "select min(vector_dims(embedding)) from soc_index_entries",
        )
    )
    group_dims = asyncio.run(
        _scalar(
            soc_database.owner_url,
            "select max(vector_dims(embedding)) from soc_unit_groups",
        )
    )

    assert dims == 384
    assert group_dims == 384


def test_a_changed_title_is_updated_in_place(soc_database: DatabaseUnderTest) -> None:
    source = _source()
    changed_first = dataclasses.replace(source.unit_groups[0], title="A renamed unit group")
    changed = dataclasses.replace(source, unit_groups=(changed_first, *source.unit_groups[1:]))
    try:
        asyncio.run(_import(soc_database.owner_url, changed))
        title = asyncio.run(
            _scalar(
                soc_database.owner_url,
                "select title from soc_unit_groups where code = :code",
                {"code": source.unit_groups[0].code},
            )
        )
        count = asyncio.run(_scalar(soc_database.owner_url, "select count(*) from soc_unit_groups"))
    finally:
        asyncio.run(_import(soc_database.owner_url, source))

    assert title == "A renamed unit group"
    assert count == 9


def test_the_rules_owned_rqf_level_survives_a_re_import(soc_database: DatabaseUnderTest) -> None:
    source = _source()
    asyncio.run(_import(soc_database.owner_url, source))
    code = source.unit_groups[0].code
    asyncio.run(
        _run(
            soc_database.owner_url,
            "update soc_unit_groups set rqf_level = '6' where code = :code",
            {"code": code},
        )
    )

    asyncio.run(_import(soc_database.owner_url, source))
    level = asyncio.run(
        _scalar(
            soc_database.owner_url,
            "select rqf_level from soc_unit_groups where code = :code",
            {"code": code},
        )
    )

    assert level == "6"


def test_the_trigram_index_on_the_index_title_exists(soc_database: DatabaseUnderTest) -> None:
    definition = asyncio.run(
        _scalar(
            soc_database.owner_url,
            "select indexdef from pg_indexes where indexname = "
            "'ix_soc_index_entries_index_title_trgm'",
        )
    )

    assert "gin" in definition
    assert "gin_trgm_ops" in definition


def test_tenants_can_read_the_reference_tables_but_not_change_them(
    soc_database: DatabaseUnderTest,
) -> None:
    asyncio.run(_import(soc_database.owner_url, _source()))

    changed = asyncio.run(_execute_as_tenant(soc_database.app_url, "delete from soc_unit_groups"))
    count = asyncio.run(_scalar(soc_database.app_url, "select count(*) from soc_unit_groups"))

    assert changed == 0
    assert count == 9
