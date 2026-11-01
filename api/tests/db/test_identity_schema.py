"""The security properties of the identity tables (T2.1), checked against a real migrated database
with raw SQL: the audit trail cannot be changed, and companies cannot see each other's rows."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from app.db.ids import uuid7
from tests.db.support import DatabaseUnderTest, engine_for, scoped_connection

COMPANY_A = uuid7()
COMPANY_B = uuid7()
USER_1 = uuid7()
USER_2 = uuid7()


async def _seed(database: DatabaseUnderTest) -> None:
    engine = engine_for(database.owner_url, poolclass=NullPool)
    try:
        async with engine.begin() as c:
            await c.execute(
                text(
                    "truncate memberships, files, notifications, users, companies restart identity cascade"
                )
            )
            for cid, slug in ((COMPANY_A, "a"), (COMPANY_B, "b")):
                await c.execute(
                    text("insert into companies (id, name, slug) values (:id, :n, :s)"),
                    {"id": cid, "n": f"Company {slug}", "s": slug},
                )
            for uid, email in ((USER_1, "One@Example.com"), (USER_2, "two@example.com")):
                await c.execute(
                    text(
                        "insert into users (id, email, first_name, last_name) values (:i, :e, 'F', 'L')"
                    ),
                    {"i": uid, "e": email},
                )
            for uid, cid in ((USER_1, COMPANY_A), (USER_2, COMPANY_B), (USER_1, COMPANY_B)):
                await c.execute(
                    text(
                        "insert into memberships (user_id, company_id, role) values (:u, :c, 'employee')"
                    ),
                    {"u": uid, "c": cid},
                )
            await c.execute(
                text(
                    "insert into files (company_id, storage_key, original_name, mime, size, sha256) "
                    "values (:c, 'k-a', 'a.pdf', 'application/pdf', 1, repeat('0', 64))"
                ),
                {"c": COMPANY_A},
            )
    finally:
        await engine.dispose()


@pytest.fixture
def seeded(database: DatabaseUnderTest) -> DatabaseUnderTest:
    asyncio.run(_seed(database))
    return database


async def _scalar(
    database: DatabaseUnderTest, sql: str, company: UUID | None, **params: object
) -> Any:
    engine = engine_for(database.app_url, poolclass=NullPool)
    try:
        async with scoped_connection(engine, company) as connection:
            return (await connection.execute(text(sql), params)).scalar_one()
    finally:
        await engine.dispose()


async def test_a_company_sees_only_its_own_memberships_and_files(seeded: DatabaseUnderTest) -> None:
    assert await _scalar(seeded, "select count(*) from memberships", COMPANY_A) == 1
    assert await _scalar(seeded, "select count(*) from memberships", COMPANY_B) == 2
    assert await _scalar(seeded, "select count(*) from files", COMPANY_A) == 1
    assert await _scalar(seeded, "select count(*) from files", COMPANY_B) == 0
    # No company set: nothing at all.
    assert await _scalar(seeded, "select count(*) from memberships", None) == 0


async def test_a_person_can_read_their_own_memberships_across_companies(
    seeded: DatabaseUnderTest,
) -> None:
    engine = engine_for(seeded.app_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("select set_config('app.user_id', :u, true)"), {"u": str(USER_1)}
            )
            count = await connection.execute(text("select count(*) from memberships"))
            assert count.scalar_one() == 2  # company A and company B, no company chosen yet
    finally:
        await engine.dispose()


async def test_an_email_is_unique_whatever_its_case(seeded: DatabaseUnderTest) -> None:
    engine = engine_for(seeded.owner_url, poolclass=NullPool)
    try:
        with pytest.raises(DBAPIError, match="unique"):
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "insert into users (email, first_name, last_name) values ('ONE@example.com', 'F', 'L')"
                    )
                )
    finally:
        await engine.dispose()


@pytest.mark.parametrize("who", ["app_url", "owner_url"])
@pytest.mark.parametrize(
    "statement",
    [
        "update audit_events set summary = 'changed'",
        "delete from audit_events",
        "truncate audit_events",
    ],
)
async def test_the_audit_trail_cannot_be_changed_or_removed(
    seeded: DatabaseUnderTest, who: str, statement: str
) -> None:
    owner = engine_for(seeded.owner_url, poolclass=NullPool)
    try:
        async with owner.begin() as connection:
            await connection.execute(
                text(
                    "insert into audit_events (company_id, actor_type, action) "
                    "values (:c, 'system', 'test.event')"
                ),
                {"c": COMPANY_A},
            )
    finally:
        await owner.dispose()

    engine = engine_for(getattr(seeded, who), poolclass=NullPool)
    try:
        with pytest.raises(DBAPIError):
            async with scoped_connection(engine, COMPANY_A) as connection:
                await connection.execute(text(statement))
        assert await _scalar(seeded, "select count(*) from audit_events", COMPANY_A) >= 1
    finally:
        await engine.dispose()


async def test_the_api_may_add_audit_events_for_its_own_company_only(
    seeded: DatabaseUnderTest,
) -> None:
    insert = "insert into audit_events (company_id, actor_type, action) values (:c, 'user', 'x.y')"
    engine = engine_for(seeded.app_url, poolclass=NullPool)
    try:
        async with scoped_connection(engine, COMPANY_A) as connection:
            await connection.execute(text(insert), {"c": COMPANY_A})
        with pytest.raises(DBAPIError):
            async with scoped_connection(engine, COMPANY_A) as connection:
                await connection.execute(text(insert), {"c": COMPANY_B})
        with pytest.raises(
            DBAPIError
        ):  # platform events (no company) are not for a company to write
            async with scoped_connection(engine, COMPANY_A) as connection:
                await connection.execute(text(insert), {"c": None})
    finally:
        await engine.dispose()


async def test_a_global_session_with_a_user_reads_that_users_memberships(
    seeded: DatabaseUnderTest,
) -> None:
    from sqlalchemy import select

    from app.db.session import GlobalSession
    from app.modules.identity.models import Membership

    engine = engine_for(seeded.app_url, poolclass=NullPool)
    try:
        async with GlobalSession(engine, user_id=USER_2) as session:
            rows = (await session.execute(select(Membership))).scalars().all()
            assert [row.company_id for row in rows] == [COMPANY_B]
        async with GlobalSession(engine) as session:  # does not say who it is: sees nothing
            assert (await session.execute(select(Membership))).scalars().all() == []
    finally:
        await engine.dispose()
