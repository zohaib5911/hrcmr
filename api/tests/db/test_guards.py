"""The drift guards: they must stay green for the real schema and go red for a bad one."""

from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.pool import NullPool

from app.db.rls import (
    PRE_TENANT_TABLES,
    materialized_views,
    security_definer_functions,
    tables_missing_tenant_rls,
    tables_missing_updated_at_trigger,
    views_bypassing_rls,
)
from tests.db.support import DatabaseUnderTest, engine_for, temporary_database


async def test_the_migrated_schema_passes_every_guard(database: DatabaseUnderTest) -> None:
    engine = engine_for(database.owner_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            assert await tables_missing_tenant_rls(connection) == []
            assert await tables_missing_updated_at_trigger(connection) == []
            assert await views_bypassing_rls(connection) == []
            assert await materialized_views(connection) == []
            assert await security_definer_functions(connection) == []
    finally:
        await engine.dispose()


def test_guards_can_exempt_a_table_explicitly() -> None:
    async def check(owner_url: str) -> None:
        engine = engine_for(owner_url, poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text("create table global_thing (id uuid primary key, company_id uuid)")
                )
            async with engine.connect() as connection:
                assert await tables_missing_tenant_rls(connection) == ["global_thing"]
                exempt = PRE_TENANT_TABLES | {"global_thing"}
                assert await tables_missing_tenant_rls(connection, exempt=exempt) == []
                # Without any exemption the two pre-tenant tables show up too.
                assert await tables_missing_tenant_rls(connection, exempt=frozenset()) == [
                    "global_thing",
                    "invitations",
                    "sessions",
                ]
        finally:
            await engine.dispose()

    with temporary_database() as db:
        asyncio.run(check(db.owner_url))
