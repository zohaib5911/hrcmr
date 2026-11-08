"""T15.7: the daily rules watch adds a draft only when a GOV.UK page has changed, and never publishes.

The pages are served by a fake transport, from the saved copies in data/raw/rules, so nothing goes
out to the network. Each test has its own database with the saved rules published as version 1."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import NullPool

from app.modules.soc_rules.importer import import_rules_source, publish_rules_version
from app.modules.soc_rules.source import (
    PAGE_KINDS,
    SKILLED_OCCUPATIONS,
    RulesSource,
    load_rules_source,
)
from app.modules.soc_rules.watch import WatchResult, watch_rules
from tests.db.support import DatabaseUnderTest, engine_for, temporary_database

RULES = Path(__file__).resolve().parents[3] / "data" / "raw" / "rules"
DATE = "2026-10-29"


def _sidecar(kind: str) -> dict[str, str]:
    data: dict[str, str] = json.loads(
        (RULES / f"appendix-{kind}-{DATE}.json").read_text(encoding="utf-8")
    )
    return data


def _urls() -> dict[str, str]:
    return {kind: str(_sidecar(kind)["source_url"]) for kind in PAGE_KINDS}


def _bodies() -> dict[str, bytes]:
    """The saved pages, keyed by the URL the live version was made from."""
    return {
        _urls()[kind]: (RULES / f"appendix-{kind}-{DATE}.html").read_bytes() for kind in PAGE_KINDS
    }


def _source() -> RulesSource:
    return load_rules_source(
        {
            kind: (
                RULES / f"appendix-{kind}-{DATE}.html",
                RULES / f"appendix-{kind}-{DATE}.json",
            )
            for kind in PAGE_KINDS
        }
    )


async def _publish_first(url: str) -> None:
    engine = engine_for(url, poolclass=NullPool, hide_parameters=True)
    try:
        async with AsyncSession(engine) as db:
            result = await import_rules_source(db, _source())
            assert result.version_id is not None
            await publish_rules_version(db, result.version_id)
            await db.commit()
    finally:
        await engine.dispose()


async def _watch(
    url: str,
    bodies: dict[str, bytes],
    status: int = 200,
    requested: list[str] | None = None,
) -> WatchResult:
    def handler(request: httpx.Request) -> httpx.Response:
        if requested is not None:
            requested.append(str(request.url))
        if status != 200:
            return httpx.Response(status)
        return httpx.Response(200, content=bodies[str(request.url)])

    engine = engine_for(url, poolclass=NullPool, hide_parameters=True)
    try:
        async with AsyncSession(engine) as db:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                result = await watch_rules(db, client, today=dt.date(2026, 11, 8))
            await db.commit()
        return result
    finally:
        await engine.dispose()


async def _stored_url_moved(url: str, kind: str, moved_to: str) -> None:
    """Points the live version's stored address for ``kind`` at another host (as bad data could)."""
    engine = engine_for(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "update rules_versions set source_urls = (select jsonb_agg(case "
                    "when e->>'kind' = :kind then jsonb_set(e, '{url}', to_jsonb(cast(:to as text))) "
                    "else e end) from jsonb_array_elements(source_urls) e) where status = 'live'"
                ),
                {"kind": kind, "to": moved_to},
            )
    finally:
        await engine.dispose()


async def _statuses(url: str) -> list[str]:
    engine = engine_for(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(
                text("select status from rules_versions order by status")
            )
            return [str(row[0]) for row in rows.all()]
    finally:
        await engine.dispose()


@pytest.fixture
def rules_database(stack: None) -> Iterator[DatabaseUnderTest]:
    with temporary_database() as db:
        asyncio.run(_publish_first(db.owner_url))
        yield db


def test_unchanged_pages_add_no_draft(rules_database: DatabaseUnderTest) -> None:
    result = asyncio.run(_watch(rules_database.owner_url, _bodies()))
    assert result.status == "unchanged"
    assert asyncio.run(_statuses(rules_database.owner_url)) == ["live"]


def test_a_changed_page_adds_a_draft_and_the_live_version_stays(
    rules_database: DatabaseUnderTest,
) -> None:
    bodies = _bodies()
    changed = _urls()[SKILLED_OCCUPATIONS]
    bodies[changed] = bodies[changed] + b"\n<!-- revised by GOV.UK -->\n"
    result = asyncio.run(_watch(rules_database.owner_url, bodies))
    assert result.status == "draft_created"
    assert result.version_id is not None
    # Nothing is published by the watch: the draft waits for a platform admin.
    assert asyncio.run(_statuses(rules_database.owner_url)) == ["draft", "live"]


def test_a_failed_fetch_changes_nothing(rules_database: DatabaseUnderTest) -> None:
    result = asyncio.run(_watch(rules_database.owner_url, _bodies(), status=503))
    assert result.status == "fetch_failed"
    assert asyncio.run(_statuses(rules_database.owner_url)) == ["live"]


def test_a_stored_address_on_another_host_is_never_requested(
    rules_database: DatabaseUnderTest,
) -> None:
    asyncio.run(
        _stored_url_moved(
            rules_database.owner_url, SKILLED_OCCUPATIONS, "https://evil.example/rules"
        )
    )
    requested: list[str] = []
    result = asyncio.run(_watch(rules_database.owner_url, _bodies(), requested=requested))
    assert result.status == "fetch_failed"
    assert requested == []
    assert asyncio.run(_statuses(rules_database.owner_url)) == ["live"]
