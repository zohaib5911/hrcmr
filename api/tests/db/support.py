"""Helpers for database tests: throwaway databases provisioned and migrated by the real code."""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from alembic import command
from app.cli import alembic_config
from app.db.provision import provision_database
from app.db.roles import APP_ROLE, OWNER_ROLE
from tests.support import TEST_DATABASE_URL

# Roles are cluster-wide, so every test database must use the SAME passwords for the whole run;
# provisioning a second database with different ones would lock out the first. Tests that rotate
# a password on purpose get the standard one restored when they finish.
STANDARD_OWNER_PASSWORD = secrets.token_urlsafe(24)
STANDARD_APP_PASSWORD = secrets.token_urlsafe(24)


@dataclass(frozen=True)
class DatabaseUnderTest:
    name: str
    admin_url: str  # superuser, connected to this database
    owner_url: str  # app_owner
    app_url: str  # app_user
    owner_password: str
    app_password: str


def _url(database: str, *, user: str | None = None, password: str | None = None) -> str:
    url = make_url(TEST_DATABASE_URL).set(database=database)
    if user:
        url = url.set(username=user, password=password)
    return url.render_as_string(hide_password=False)


def admin_engine(database: str = "postgres") -> AsyncEngine:
    return create_async_engine(_url(database), isolation_level="AUTOCOMMIT", poolclass=NullPool)


async def _create_database(name: str) -> None:
    engine = admin_engine()
    try:
        async with engine.connect() as connection:
            await connection.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        await engine.dispose()


async def _drop_database(name: str) -> None:
    engine = admin_engine()
    try:
        async with engine.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    finally:
        await engine.dispose()


@contextmanager
def temporary_database(
    *,
    provision: bool = True,
    migrate: bool = True,
    owner_password: str | None = None,
    app_password: str | None = None,
) -> Iterator[DatabaseUnderTest]:
    """A fresh database on the disposable test server, optionally provisioned and migrated."""
    name = f"brand_t_{secrets.token_hex(6)}"
    owner_password = owner_password or STANDARD_OWNER_PASSWORD
    app_password = app_password or STANDARD_APP_PASSWORD
    database = DatabaseUnderTest(
        name=name,
        admin_url=_url(name),
        owner_url=_url(name, user=OWNER_ROLE, password=owner_password),
        app_url=_url(name, user=APP_ROLE, password=app_password),
        owner_password=owner_password,
        app_password=app_password,
    )
    asyncio.run(_create_database(name))
    try:
        if provision:
            asyncio.run(
                provision_database(
                    database.admin_url,
                    database=name,
                    owner_password=owner_password,
                    app_password=app_password,
                )
            )
            if migrate:
                command.upgrade(alembic_config(database.owner_url), "head")
        yield database
    finally:
        if provision and (owner_password, app_password) != (
            STANDARD_OWNER_PASSWORD,
            STANDARD_APP_PASSWORD,
        ):
            asyncio.run(
                provision_database(
                    database.admin_url,
                    database=name,
                    owner_password=STANDARD_OWNER_PASSWORD,
                    app_password=STANDARD_APP_PASSWORD,
                )
            )
        asyncio.run(_drop_database(name))


def engine_for(url: str, **kwargs: Any) -> AsyncEngine:
    return create_async_engine(url, **kwargs)


async def set_company(connection: AsyncConnection, company_id: UUID | str) -> None:
    """What a tenant session does at the start of every transaction."""
    await connection.execute(
        text("select set_config('app.company_id', :c, true)"), {"c": str(company_id)}
    )


@asynccontextmanager
async def scoped_connection(
    engine: AsyncEngine, company_id: UUID | None
) -> AsyncIterator[AsyncConnection]:
    """A connection in a transaction scoped to ``company_id`` (or to nothing)."""
    async with engine.begin() as connection:
        if company_id is not None:
            await set_company(connection, company_id)
        yield connection


def settings_environment(monkeypatch: pytest.MonkeyPatch, database: DatabaseUnderTest) -> None:
    """Point the process environment (and so ``get_settings()``) at a test database."""
    from app.core.config import get_settings
    from tests.support import build_settings

    base = build_settings()
    values = {
        "APP_ENV": "test",
        "DOMAIN": "localhost",
        "WEB_ORIGIN": base.web_origin,
        "ADMIN_ORIGIN": base.admin_origin,
        "API_ORIGIN": base.api_origin,
        "DATABASE_URL": database.app_url,
        "DATABASE_URL_OWNER": database.owner_url,
        "DATABASE_URL_ADMIN": database.admin_url,
        "REDIS_URL": base.redis_url.get_secret_value(),
        "SESSION_SECRET": base.session_secret.get_secret_value(),
        "FIELD_ENCRYPTION_KEYS": base.field_encryption_keys.get_secret_value(),
        "BLIND_INDEX_KEY": base.blind_index_key.get_secret_value(),
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
