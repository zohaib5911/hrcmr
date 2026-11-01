from __future__ import annotations

import asyncio
import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.db.ids import uuid7, uuid7_datetime
from tests.db.support import DatabaseUnderTest, engine_for


def test_python_uuid7_is_a_valid_version_7_uuid() -> None:
    value = uuid7()
    assert value.version == 7
    assert value.variant == uuid.RFC_4122


def test_python_uuid7_embeds_the_current_time() -> None:
    before = datetime.now(UTC) - timedelta(seconds=1)
    created = uuid7_datetime(uuid7())
    assert before <= created <= datetime.now(UTC) + timedelta(seconds=1)


def test_python_uuid7_sorts_by_creation_time() -> None:
    first = uuid7()
    time.sleep(0.005)
    second = uuid7()
    time.sleep(0.005)
    third = uuid7()
    assert first < second < third


def test_python_uuid7_is_unique_and_unguessable_enough() -> None:
    values = {uuid7() for _ in range(20_000)}
    assert len(values) == 20_000
    # 74 random bits: the random parts of consecutive ids must differ.
    assert uuid7().bytes[7:] != uuid7().bytes[7:]


def test_uuid7_datetime_rejects_other_versions() -> None:
    with pytest.raises(ValueError, match="version 7"):
        uuid7_datetime(uuid.uuid4())


async def test_database_function_makes_version_7_uuids(database: DatabaseUnderTest) -> None:
    engine = engine_for(database.app_url)
    try:
        async with engine.connect() as connection:
            rows = (
                (
                    await connection.execute(
                        text("select uuid_generate_v7() from generate_series(1, 2000)")
                    )
                )
                .scalars()
                .all()
            )
    finally:
        await engine.dispose()
    assert len(set(rows)) == 2000
    assert all(v.version == 7 and v.variant == uuid.RFC_4122 for v in rows)
    now = datetime.now(UTC)
    assert all(abs((uuid7_datetime(v) - now).total_seconds()) < 10 for v in rows)


async def test_database_function_is_time_ordered_across_statements(
    database: DatabaseUnderTest,
) -> None:
    engine = engine_for(database.app_url)
    try:
        async with engine.connect() as connection:
            first = (await connection.execute(text("select uuid_generate_v7()"))).scalar_one()
            await asyncio.sleep(0.01)
            second = (await connection.execute(text("select uuid_generate_v7()"))).scalar_one()
    finally:
        await engine.dispose()
    assert first < second
