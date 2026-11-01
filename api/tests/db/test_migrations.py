from __future__ import annotations

import asyncio

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from alembic import command
from app.cli import alembic_config
from tests.db.support import engine_for, temporary_database

FUNCTIONS = {"uuid_generate_v7", "app_current_company_id", "set_updated_at"}


async def _query(url: str, sql: str) -> list[str]:
    engine = engine_for(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            return sorted(str(v) for v in (await connection.execute(text(sql))).scalars())
    finally:
        await engine.dispose()


def _functions(url: str) -> set[str]:
    sql = (
        "select p.proname from pg_proc p join pg_namespace n on n.oid = p.pronamespace "
        "where n.nspname = 'public' and p.proname = any(array['uuid_generate_v7', "
        "'app_current_company_id', 'set_updated_at'])"
    )
    return set(asyncio.run(_query(url, sql)))


def test_migrations_apply_roll_back_and_apply_again_cleanly() -> None:
    with temporary_database(migrate=False) as db:
        config = alembic_config(db.owner_url)
        assert _functions(db.owner_url) == set()

        command.upgrade(config, "head")
        assert _functions(db.owner_url) == FUNCTIONS
        assert asyncio.run(_query(db.owner_url, "select version_num from alembic_version")) == [
            "0001_foundations"
        ]

        command.downgrade(config, "base")
        assert _functions(db.owner_url) == set()

        command.upgrade(config, "head")
        assert _functions(db.owner_url) == FUNCTIONS


def test_the_models_and_the_migrations_agree() -> None:
    """`alembic check` fails if a model changed without a migration."""
    with temporary_database() as db:
        command.check(alembic_config(db.owner_url))


def test_history_is_a_single_line() -> None:
    script = ScriptDirectory.from_config(alembic_config())
    assert len(script.get_heads()) == 1


@pytest.mark.parametrize("who", ["app_url", "admin_url"])
def test_migrations_refuse_to_run_as_anyone_but_the_owner(who: str) -> None:
    with temporary_database(migrate=False) as db:
        with pytest.raises(RuntimeError, match="must run as app_owner"):
            command.upgrade(alembic_config(getattr(db, who)), "head")
        assert _functions(db.owner_url) == set()


def test_upgrade_works_on_a_database_that_was_provisioned_but_never_migrated() -> None:
    with temporary_database(migrate=False) as db:
        command.upgrade(alembic_config(db.owner_url), "head")
        command.upgrade(alembic_config(db.owner_url), "head")  # running it twice is harmless
