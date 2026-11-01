"""The Done-when of T0.5: company A can never read or write company B's rows, even with raw SQL
as ``app_user``. Everything here talks to PostgreSQL directly: no ORM, no application filters."""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.pool import NullPool

from app.db.ids import uuid7
from app.db.rls import (
    create_tenant_view_statements,
    materialized_views,
    security_definer_functions,
    tenant_rls_statements,
    views_bypassing_rls,
)
from tests.db.support import (
    DatabaseUnderTest,
    admin_engine,
    engine_for,
    scoped_connection,
    set_company,
)

COMPANY_A = uuid7()
COMPANY_B = uuid7()
ROWS_A = ["a-1", "a-2", "a-3"]
ROWS_B = ["b-1", "b-2"]


async def _seed(database: DatabaseUnderTest) -> None:
    engine = engine_for(database.owner_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("drop table if exists tenant_probe"))
            await connection.execute(
                text(
                    "create table tenant_probe (id uuid primary key default uuid_generate_v7(), "
                    "company_id uuid not null, label text not null)"
                )
            )
            for statement in tenant_rls_statements("tenant_probe"):
                await connection.execute(text(statement))
            for company, labels in ((COMPANY_A, ROWS_A), (COMPANY_B, ROWS_B)):
                for label in labels:
                    await connection.execute(
                        text("insert into tenant_probe (company_id, label) values (:c, :l)"),
                        {"c": company, "l": label},
                    )
    finally:
        await engine.dispose()


@pytest.fixture
def probe(database: DatabaseUnderTest) -> DatabaseUnderTest:
    """Re-seed before each test so tests that write cannot affect each other."""
    asyncio.run(_seed(database))
    return database


async def _owner_labels(database: DatabaseUnderTest) -> list[str]:
    engine = engine_for(database.owner_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(text("select label from tenant_probe order by label"))
            return list(rows.scalars())
    finally:
        await engine.dispose()


async def _labels(database: DatabaseUnderTest, company: UUID | None) -> list[str]:
    engine = engine_for(database.app_url, poolclass=NullPool)
    try:
        async with scoped_connection(engine, company) as connection:
            rows = await connection.execute(text("select label from tenant_probe order by label"))
            return list(rows.scalars())
    finally:
        await engine.dispose()


# --- Reads -------------------------------------------------------------------------------------------


async def test_each_company_sees_only_its_own_rows(probe: DatabaseUnderTest) -> None:
    assert await _labels(probe, COMPANY_A) == ROWS_A
    assert await _labels(probe, COMPANY_B) == ROWS_B


async def test_asking_for_another_companys_rows_returns_nothing(probe: DatabaseUnderTest) -> None:
    engine = engine_for(probe.app_url, poolclass=NullPool)
    try:
        async with scoped_connection(engine, COMPANY_A) as connection:
            by_filter = await connection.execute(
                text("select count(*) from tenant_probe where company_id = :b"), {"b": COMPANY_B}
            )
            by_label = await connection.execute(
                text("select count(*) from tenant_probe where label = 'b-1'")
            )
            union = await connection.execute(
                text(
                    "select count(*) from (select * from tenant_probe union all select * from tenant_probe) t where company_id = :b"
                ),
                {"b": COMPANY_B},
            )
            assert by_filter.scalar_one() == 0
            assert by_label.scalar_one() == 0
            assert union.scalar_one() == 0
    finally:
        await engine.dispose()


async def test_with_no_company_set_nothing_is_visible(probe: DatabaseUnderTest) -> None:
    assert await _labels(probe, None) == []


async def test_an_empty_company_setting_fails_closed_without_an_error(
    probe: DatabaseUnderTest,
) -> None:
    engine = engine_for(probe.app_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("select set_config('app.company_id', '', true)"))
            rows = await connection.execute(text("select count(*) from tenant_probe"))
            assert rows.scalar_one() == 0
    finally:
        await engine.dispose()


async def test_a_malformed_company_setting_is_an_error_not_a_leak(probe: DatabaseUnderTest) -> None:
    engine = engine_for(probe.app_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            await connection.execute(
                text("select set_config('app.company_id', 'not-a-uuid', false)")
            )
            with pytest.raises(DBAPIError):
                await connection.execute(text("select * from tenant_probe"))
    finally:
        await engine.dispose()


# --- Writes ------------------------------------------------------------------------------------------


async def test_update_without_a_where_clause_only_touches_own_rows(
    probe: DatabaseUnderTest,
) -> None:
    engine = engine_for(probe.app_url, poolclass=NullPool)
    try:
        async with scoped_connection(engine, COMPANY_A) as connection:
            result = await connection.execute(text("update tenant_probe set label = 'hacked'"))
            assert result.rowcount == len(ROWS_A)
    finally:
        await engine.dispose()
    assert await _owner_labels(probe) == sorted(["hacked"] * 3 + ROWS_B)


async def test_update_aimed_at_another_company_changes_nothing(probe: DatabaseUnderTest) -> None:
    engine = engine_for(probe.app_url, poolclass=NullPool)
    try:
        async with scoped_connection(engine, COMPANY_A) as connection:
            result = await connection.execute(
                text("update tenant_probe set label = 'hacked' where company_id = :b"),
                {"b": COMPANY_B},
            )
            assert result.rowcount == 0
    finally:
        await engine.dispose()
    assert await _owner_labels(probe) == sorted(ROWS_A + ROWS_B)


async def test_delete_only_removes_own_rows(probe: DatabaseUnderTest) -> None:
    engine = engine_for(probe.app_url, poolclass=NullPool)
    try:
        async with scoped_connection(engine, COMPANY_A) as connection:
            result = await connection.execute(text("delete from tenant_probe"))
            assert result.rowcount == len(ROWS_A)
    finally:
        await engine.dispose()
    assert await _owner_labels(probe) == ROWS_B


async def test_inserting_a_row_for_another_company_is_refused(probe: DatabaseUnderTest) -> None:
    engine = engine_for(probe.app_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            await set_company(connection, COMPANY_A)
            with pytest.raises(DBAPIError, match="row-level security"):
                await connection.execute(
                    text("insert into tenant_probe (company_id, label) values (:b, 'planted')"),
                    {"b": COMPANY_B},
                )
            await transaction.rollback()
    finally:
        await engine.dispose()
    assert await _owner_labels(probe) == sorted(ROWS_A + ROWS_B)


async def test_moving_a_row_to_another_company_is_refused(probe: DatabaseUnderTest) -> None:
    engine = engine_for(probe.app_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            await set_company(connection, COMPANY_A)
            with pytest.raises(DBAPIError, match="row-level security"):
                await connection.execute(
                    text("update tenant_probe set company_id = :b where label = 'a-1'"),
                    {"b": COMPANY_B},
                )
            await transaction.rollback()
    finally:
        await engine.dispose()


async def test_inserting_for_your_own_company_works_and_gets_a_version_7_id(
    probe: DatabaseUnderTest,
) -> None:
    engine = engine_for(probe.app_url, poolclass=NullPool)
    try:
        async with scoped_connection(engine, COMPANY_A) as connection:
            new_id = (
                await connection.execute(
                    text(
                        "insert into tenant_probe (company_id, label) values (:a, 'a-4') returning id"
                    ),
                    {"a": COMPANY_A},
                )
            ).scalar_one()
    finally:
        await engine.dispose()
    assert new_id.version == 7
    assert "a-4" in await _owner_labels(probe)


# --- Isolation holds across connection reuse and concurrency ----------------------------------------


async def test_the_company_does_not_leak_to_the_next_user_of_a_pooled_connection(
    probe: DatabaseUnderTest,
) -> None:
    engine = engine_for(probe.app_url, pool_size=1, max_overflow=0)
    try:
        async with scoped_connection(engine, COMPANY_A) as connection:
            pid_first = (await connection.execute(text("select pg_backend_pid()"))).scalar_one()
            assert (
                await connection.execute(text("select count(*) from tenant_probe"))
            ).scalar_one() == 3
        async with engine.begin() as connection:  # same physical connection, nobody set a company
            pid_second = (await connection.execute(text("select pg_backend_pid()"))).scalar_one()
            seen = (
                await connection.execute(text("select count(*) from tenant_probe"))
            ).scalar_one()
            setting = (
                await connection.execute(text("select app_current_company_id()"))
            ).scalar_one()
        assert pid_first == pid_second
        assert seen == 0
        assert setting is None
    finally:
        await engine.dispose()


async def test_concurrent_companies_never_see_each_other(probe: DatabaseUnderTest) -> None:
    engine = engine_for(probe.app_url, pool_size=5, max_overflow=5)

    async def worker(company: UUID, expected: int) -> bool:
        for _ in range(30):
            async with scoped_connection(engine, company) as connection:
                rows = await connection.execute(text("select company_id from tenant_probe"))
                ids = set(rows.scalars())
                if len(ids) > 1 or (ids and ids != {company}):
                    return False
                count = (
                    await connection.execute(text("select count(*) from tenant_probe"))
                ).scalar_one()
                if count != expected:
                    return False
        return True

    try:
        results = await asyncio.gather(
            *(worker(COMPANY_A, 3) for _ in range(4)), *(worker(COMPANY_B, 2) for _ in range(4))
        )
    finally:
        await engine.dispose()
    assert all(results)


# --- The runtime role cannot talk its way out of it -------------------------------------------------


async def test_app_user_has_no_privileges_that_bypass_row_level_security(
    probe: DatabaseUnderTest,
) -> None:
    engine = admin_engine(probe.name)
    try:
        async with engine.connect() as connection:
            roles = {
                name: (superuser, bypass, create_role, create_db)
                for name, superuser, bypass, create_role, create_db in (
                    await connection.execute(
                        text(
                            "select rolname, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb "
                            "from pg_roles where rolname in ('app_user', 'app_owner')"
                        )
                    )
                )
            }
            owner = (
                await connection.execute(
                    text("select tableowner from pg_tables where tablename = 'tenant_probe'")
                )
            ).scalar_one()
    finally:
        await engine.dispose()
    assert roles["app_user"] == (False, False, False, False)
    assert roles["app_owner"] == (False, False, False, False)
    assert owner == "app_owner"


async def test_the_policy_covers_every_command_for_app_user_only(probe: DatabaseUnderTest) -> None:
    engine = admin_engine(probe.name)
    try:
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        "select policyname, cmd, roles, qual, with_check from pg_policies "
                        "where tablename = 'tenant_probe'"
                    )
                )
            ).all()
            rls_on = (
                await connection.execute(
                    text("select relrowsecurity from pg_class where relname = 'tenant_probe'")
                )
            ).scalar_one()
    finally:
        await engine.dispose()
    assert rls_on is True
    assert len(rows) == 1
    name, cmd, roles, qual, with_check = rows[0]
    assert name == "tenant_isolation"
    assert cmd == "ALL"
    assert list(roles) == ["app_user"]
    assert qual
    assert qual == with_check


@pytest.mark.parametrize(
    "statement",
    [
        "alter table tenant_probe disable row level security",
        "alter table tenant_probe no force row level security",
        "drop policy tenant_isolation on tenant_probe",
        "create table sneaky (id int)",
        "create role escalated login",
        "set role app_owner",
        "set session authorization postgres",
        "alter role app_user bypassrls",
        "drop table tenant_probe",
        "truncate tenant_probe",
    ],
)
async def test_app_user_cannot_change_the_rules(probe: DatabaseUnderTest, statement: str) -> None:
    engine = engine_for(probe.app_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            with pytest.raises(
                ProgrammingError, match=r"permission denied|must be owner|not permitted"
            ):
                await connection.execute(text(statement))
    finally:
        await engine.dispose()


async def test_switching_row_security_off_makes_queries_fail_instead_of_leak(
    probe: DatabaseUnderTest,
) -> None:
    engine = engine_for(probe.app_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("set row_security = off"))
            with pytest.raises(DBAPIError, match="row-level security"):
                await connection.execute(text("select * from tenant_probe"))
    finally:
        await engine.dispose()


async def _count_via_view(database: DatabaseUnderTest, company: UUID, view_sql: list[str]) -> int:
    owner = engine_for(database.owner_url, poolclass=NullPool)
    app = engine_for(database.app_url, poolclass=NullPool)
    try:
        async with owner.begin() as connection:
            await connection.execute(text("drop view if exists probe_view"))
            for statement in view_sql:
                await connection.execute(text(statement))
        async with scoped_connection(app, company) as connection:
            count: int = (
                await connection.execute(text("select count(*) from probe_view"))
            ).scalar_one()
            return count
    finally:
        async with owner.begin() as connection:
            await connection.execute(text("drop view if exists probe_view"))
        await owner.dispose()
        await app.dispose()


async def test_a_plain_view_leaks_every_companys_rows_which_is_why_the_helper_exists(
    probe: DatabaseUnderTest,
) -> None:
    """Documents the hazard. A view runs as its owner, who is not subject to the policy."""
    plain = [
        "create view probe_view as select * from tenant_probe",
        "grant select on probe_view to app_user",
    ]
    assert await _count_via_view(probe, COMPANY_B, plain) == len(ROWS_A) + len(ROWS_B)


async def test_a_tenant_view_applies_the_callers_policy(probe: DatabaseUnderTest) -> None:
    safe = create_tenant_view_statements("probe_view", "select * from tenant_probe")
    assert await _count_via_view(probe, COMPANY_A, safe) == len(ROWS_A)
    assert await _count_via_view(probe, COMPANY_B, safe) == len(ROWS_B)


async def test_the_guards_catch_unsafe_views_materialised_views_and_definer_functions(
    probe: DatabaseUnderTest,
) -> None:
    owner = engine_for(probe.owner_url, poolclass=NullPool)
    try:
        async with owner.begin() as connection:
            await connection.execute(text("create view unsafe_view as select * from tenant_probe"))
            await connection.execute(
                text(
                    "create view safe_view with (security_invoker = true) as select * from tenant_probe"
                )
            )
            await connection.execute(
                text("create materialized view cached_probe as select * from tenant_probe")
            )
            await connection.execute(
                text(
                    "create function leaky() returns bigint language sql security definer "
                    "as 'select count(*) from tenant_probe'"
                )
            )
        async with owner.connect() as connection:
            assert await views_bypassing_rls(connection) == ["unsafe_view"]
            assert await materialized_views(connection) == ["cached_probe"]
            assert await security_definer_functions(connection) == ["leaky"]
            assert await views_bypassing_rls(connection, exempt=frozenset({"unsafe_view"})) == []
    finally:
        async with owner.begin() as connection:
            for statement in (
                "drop view if exists unsafe_view",
                "drop view if exists safe_view",
                "drop materialized view if exists cached_probe",
                "drop function if exists leaky()",
            ):
                await connection.execute(text(statement))
        await owner.dispose()
