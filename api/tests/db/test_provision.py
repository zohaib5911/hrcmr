from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.pool import NullPool

from app.db.provision import provision_database
from app.db.roles import EXTENSIONS
from tests.db.support import admin_engine, engine_for, temporary_database


async def _scalar(url: str, sql: str) -> object:
    engine = engine_for(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            return (await connection.execute(text(sql))).scalar_one()
    finally:
        await engine.dispose()


def test_provisioning_sets_up_roles_ownership_and_extensions() -> None:
    with temporary_database(migrate=False) as db:
        owner_of_db = asyncio.run(
            _scalar(
                db.admin_url,
                "select pg_get_userbyid(datdba) from pg_database where datname = current_database()",
            )
        )
        owner_of_schema = asyncio.run(
            _scalar(
                db.admin_url,
                "select pg_get_userbyid(nspowner) from pg_namespace where nspname = 'public'",
            )
        )
        installed = asyncio.run(
            _scalar(
                db.admin_url, "select string_agg(extname, ',' order by extname) from pg_extension"
            )
        )
        assert owner_of_db == "app_owner"
        assert owner_of_schema == "app_owner"
        assert all(extension in str(installed) for extension in EXTENSIONS)
        assert asyncio.run(_scalar(db.owner_url, "select current_user")) == "app_owner"
        assert asyncio.run(_scalar(db.app_url, "select current_user")) == "app_user"


def test_runtime_role_gets_safety_timeouts_and_cannot_create_objects() -> None:
    with temporary_database(migrate=False) as db:
        assert asyncio.run(_scalar(db.app_url, "show statement_timeout")) == "1min"
        assert asyncio.run(_scalar(db.app_url, "show idle_in_transaction_session_timeout")) == "30s"

        async def try_create() -> None:
            engine = engine_for(db.app_url, poolclass=NullPool)
            try:
                async with engine.connect() as connection:
                    await connection.execute(text("create table nope (id int)"))
            finally:
                await engine.dispose()

        with pytest.raises(ProgrammingError, match="permission denied"):
            asyncio.run(try_create())


def test_other_roles_cannot_even_connect_to_the_database() -> None:
    with temporary_database(migrate=False) as db:

        async def create_outsider() -> None:
            engine = admin_engine()
            try:
                async with engine.connect() as connection:
                    await connection.execute(text("drop role if exists outsider"))
                    await connection.execute(
                        text("create role outsider login password 'outsider-pw-1'")
                    )
            finally:
                await engine.dispose()

        async def connect_as_outsider() -> None:
            url = db.admin_url.replace("postgres:postgres", "outsider:outsider-pw-1")
            await _scalar(url, "select 1")

        asyncio.run(create_outsider())
        with pytest.raises(DBAPIError, match="permission denied for database"):
            asyncio.run(connect_as_outsider())


def test_provisioning_is_idempotent_and_rotates_passwords() -> None:
    with temporary_database(migrate=False) as db:
        asyncio.run(
            provision_database(
                db.admin_url,
                database=db.name,
                owner_password="new-owner-pw-1",
                app_password="new-app-pw-1",
            )
        )
        try:
            new_app_url = db.app_url.replace(db.app_password, "new-app-pw-1")
            assert asyncio.run(_scalar(new_app_url, "select current_user")) == "app_user"
            with pytest.raises(DBAPIError, match="password authentication failed"):
                asyncio.run(_scalar(db.app_url, "select 1"))  # the old password no longer works
        finally:  # roles are cluster-wide: put the run's standard passwords back
            asyncio.run(
                provision_database(
                    db.admin_url,
                    database=db.name,
                    owner_password=db.owner_password,
                    app_password=db.app_password,
                )
            )


def test_awkward_passwords_are_handled_safely() -> None:
    owner = "o'wner\"pw:with%odd\\chars;--"
    app = "a'pp$$pw%s:@/?#[]{}"
    with temporary_database(migrate=False, owner_password=owner, app_password=app) as db:
        assert asyncio.run(_scalar(db.owner_url, "select current_user")) == "app_owner"
        assert asyncio.run(_scalar(db.app_url, "select current_user")) == "app_user"


def test_empty_passwords_are_rejected() -> None:
    with pytest.raises(ValueError, match="passwords are required"):
        asyncio.run(
            provision_database(
                "postgresql+asyncpg://x@localhost/x",
                database="x",
                owner_password="",
                app_password="y",
            )
        )
