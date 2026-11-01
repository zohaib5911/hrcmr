"""The application half of tenant isolation: TenantSession scopes queries, stamps writes and
refuses cross-company changes. Each guarantee is proved independently of Row-Level Security by
running the session on the OWNER connection, which RLS does not apply to."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import MetaData, String, delete, func, select, text, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import NullPool

from app.db.base import NAMING_CONVENTION, RecordMixin, TenantMixin
from app.db.ids import uuid7
from app.db.rls import tenant_rls_statements, updated_at_trigger_statements
from app.db.session import GlobalSession, TenantSession, TenantViolationError
from tests.db.support import DatabaseUnderTest, engine_for

COMPANY_A, COMPANY_B = uuid7(), uuid7()
USER_1, USER_2 = uuid7(), uuid7()


class ProbeBase(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Widget(ProbeBase, RecordMixin, TenantMixin):
    __tablename__ = "widget"
    name: Mapped[str] = mapped_column(String(100))


async def _prepare(database: DatabaseUnderTest) -> dict[str, uuid.UUID]:
    engine = engine_for(database.owner_url, poolclass=NullPool)
    ids: dict[str, uuid.UUID] = {}
    try:
        async with engine.begin() as connection:
            await connection.execute(text("drop table if exists widget"))
            await connection.run_sync(ProbeBase.metadata.create_all)
            for statement in [
                *tenant_rls_statements("widget"),
                *updated_at_trigger_statements("widget"),
            ]:
                await connection.execute(text(statement))
            for company, names in ((COMPANY_A, ["a-1", "a-2", "a-3"]), (COMPANY_B, ["b-1", "b-2"])):
                for name in names:
                    ids[name] = uuid7()
                    await connection.execute(
                        text("insert into widget (id, company_id, name) values (:i, :c, :n)"),
                        {"i": ids[name], "c": company, "n": name},
                    )
    finally:
        await engine.dispose()
    return ids


@pytest.fixture
def widgets(database: DatabaseUnderTest) -> dict[str, uuid.UUID]:
    return asyncio.run(_prepare(database))


async def _names(database: DatabaseUnderTest) -> list[str]:
    engine = engine_for(database.owner_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            return list(
                (await connection.execute(text("select name from widget order by name"))).scalars()
            )
    finally:
        await engine.dispose()


# --- Writes are stamped ------------------------------------------------------------------------------


async def test_new_rows_get_the_company_the_creator_and_a_version_7_id(
    database: DatabaseUnderTest, widgets: dict[str, uuid.UUID]
) -> None:
    engine = engine_for(database.app_url, poolclass=NullPool)
    try:
        async with TenantSession(engine, company_id=COMPANY_A, user_id=USER_1) as session:
            widget = Widget(name="created")  # no company, no id
            session.add(widget)
            await session.commit()
            assert widget.company_id == COMPANY_A
            assert widget.created_by == USER_1
            assert widget.updated_by == USER_1
            assert widget.id.version == 7
            assert widget.created_at is not None
            assert widget.updated_at is not None
    finally:
        await engine.dispose()
    assert "created" in await _names(database)


async def test_an_update_records_who_and_when(
    database: DatabaseUnderTest, widgets: dict[str, uuid.UUID]
) -> None:
    engine = engine_for(database.app_url, poolclass=NullPool)
    try:
        async with TenantSession(engine, company_id=COMPANY_A, user_id=USER_1) as session:
            widget = (
                await session.execute(select(Widget).where(Widget.name == "a-1"))
            ).scalar_one()
            first_updated = widget.updated_at
            await asyncio.sleep(0.01)
            widget.name = "a-1-renamed"
        async with TenantSession(engine, company_id=COMPANY_A, user_id=USER_2) as session:
            widget = (
                await session.execute(select(Widget).where(Widget.name == "a-1"))
            ).scalar_one()
            widget.name = "a-1-renamed"
            await session.commit()
            assert widget.updated_by == USER_2
            assert widget.updated_at > first_updated  # fetched back without a lazy load
    finally:
        await engine.dispose()


async def test_the_database_keeps_updated_at_current_even_for_raw_sql(
    database: DatabaseUnderTest, widgets: dict[str, uuid.UUID]
) -> None:
    engine = engine_for(database.owner_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            before = (
                await connection.execute(text("select updated_at from widget where name='a-1'"))
            ).scalar_one()
        await asyncio.sleep(0.01)
        async with engine.begin() as connection:
            await connection.execute(text("update widget set name = 'a-1' where name = 'a-1'"))
        async with engine.begin() as connection:
            after = (
                await connection.execute(text("select updated_at from widget where name='a-1'"))
            ).scalar_one()
    finally:
        await engine.dispose()
    assert after > before


# --- Layer 2 on its own: scoped even when RLS cannot help (owner connection) ------------------------


async def test_orm_queries_are_scoped_without_any_help_from_rls(
    database: DatabaseUnderTest, widgets: dict[str, uuid.UUID]
) -> None:
    engine = engine_for(database.owner_url, poolclass=NullPool)  # the owner is NOT subject to RLS
    try:
        async with TenantSession(engine, company_id=COMPANY_A) as session:
            rows = (await session.execute(select(Widget).order_by(Widget.name))).scalars().all()
            assert [w.name for w in rows] == ["a-1", "a-2", "a-3"]
            count = (await session.execute(select(func.count()).select_from(Widget))).scalar_one()
            assert count == 3
            assert await session.get(Widget, widgets["b-1"]) is None
            aliased = (
                await session.execute(select(Widget.name).where(Widget.name.like("b-%")))
            ).all()
            assert aliased == []
    finally:
        await engine.dispose()


async def test_bulk_update_and_delete_are_scoped_without_help_from_rls(
    database: DatabaseUnderTest, widgets: dict[str, uuid.UUID]
) -> None:
    engine = engine_for(database.owner_url, poolclass=NullPool)
    try:
        async with TenantSession(engine, company_id=COMPANY_A) as session:
            updated = await session.execute(update(Widget).values(name="changed"))
            assert isinstance(updated, CursorResult)
            assert updated.rowcount == 3
            await session.commit()
        assert await _names(database) == sorted(["changed"] * 3 + ["b-1", "b-2"])
        async with TenantSession(engine, company_id=COMPANY_A) as session:
            deleted = await session.execute(delete(Widget))
            assert isinstance(deleted, CursorResult)
            assert deleted.rowcount == 3
            await session.commit()
        assert await _names(database) == ["b-1", "b-2"]
    finally:
        await engine.dispose()


# --- Cross-company writes are refused before they reach the database --------------------------------


async def test_creating_a_row_for_another_company_is_refused(
    database: DatabaseUnderTest, widgets: dict[str, uuid.UUID]
) -> None:
    engine = engine_for(database.owner_url, poolclass=NullPool)
    try:
        async with TenantSession(engine, company_id=COMPANY_A) as session:
            session.add(Widget(name="smuggled", company_id=COMPANY_B))
            with pytest.raises(TenantViolationError, match="another company"):
                await session.flush()
    finally:
        await engine.dispose()
    assert "smuggled" not in await _names(database)


async def test_moving_a_row_to_another_company_is_refused(
    database: DatabaseUnderTest, widgets: dict[str, uuid.UUID]
) -> None:
    engine = engine_for(database.owner_url, poolclass=NullPool)
    try:
        async with TenantSession(engine, company_id=COMPANY_A) as session:
            widget = (
                await session.execute(select(Widget).where(Widget.name == "a-1"))
            ).scalar_one()
            widget.company_id = COMPANY_B
            with pytest.raises(TenantViolationError, match="another company"):
                await session.flush()
    finally:
        await engine.dispose()


# --- Layer 1 through the ORM: the real runtime role ------------------------------------------------------


async def test_the_scope_survives_a_mid_request_commit(
    database: DatabaseUnderTest, widgets: dict[str, uuid.UUID]
) -> None:
    """A commit ends the transaction and its SET LOCAL. The next transaction must be re-scoped."""
    engine = engine_for(database.app_url, pool_size=1, max_overflow=0)
    try:
        async with TenantSession(engine, company_id=COMPANY_A, user_id=USER_1) as session:
            session.add(Widget(name="first"))
            await session.commit()
            current = (await session.execute(text("select app_current_company_id()"))).scalar_one()
            assert current == COMPANY_A
            rows = (await session.execute(select(Widget.company_id))).scalars().all()
            assert set(rows) == {COMPANY_A}
            await session.rollback()
            current = (await session.execute(text("select app_current_company_id()"))).scalar_one()
            assert current == COMPANY_A
    finally:
        await engine.dispose()


async def test_a_global_session_sees_no_tenant_rows(
    database: DatabaseUnderTest, widgets: dict[str, uuid.UUID]
) -> None:
    engine = engine_for(database.app_url, poolclass=NullPool)
    try:
        async with GlobalSession(engine) as session:
            assert (await session.execute(select(Widget))).scalars().all() == []
            assert (
                await session.execute(text("select app_current_company_id()"))
            ).scalar_one() is None
    finally:
        await engine.dispose()


async def test_many_concurrent_sessions_stay_in_their_own_company(
    database: DatabaseUnderTest, widgets: dict[str, uuid.UUID]
) -> None:
    engine = engine_for(database.app_url, pool_size=4, max_overflow=4)

    async def read(company: uuid.UUID, expected: int) -> bool:
        for _ in range(25):
            async with TenantSession(engine, company_id=company) as session:
                found = (await session.execute(select(Widget))).scalars().all()
                if len(found) != expected or any(w.company_id != company for w in found):
                    return False
        return True

    try:
        results = await asyncio.gather(
            *(read(COMPANY_A, 3) for _ in range(6)), *(read(COMPANY_B, 2) for _ in range(6))
        )
    finally:
        await engine.dispose()
    assert all(results)


async def test_a_session_without_a_commit_leaves_nothing_behind(
    database: DatabaseUnderTest, widgets: dict[str, uuid.UUID]
) -> None:
    engine = engine_for(database.app_url, poolclass=NullPool)
    try:
        async with TenantSession(engine, company_id=COMPANY_A) as session:
            session.add(Widget(name="never-committed"))
            await session.flush()
    finally:
        await engine.dispose()
    assert "never-committed" not in await _names(database)
