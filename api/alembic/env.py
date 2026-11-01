"""Alembic environment (async). Migrations must run as `app_owner`."""

from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.registry  # noqa: F401  (registers every model on Base.metadata)
from alembic import context
from app.core.config import get_settings
from app.db.base import Base
from app.db.roles import OWNER_ROLE

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    explicit = config.attributes.get("url")
    if explicit:
        return str(explicit)
    owner_url = get_settings().database_url_owner
    if owner_url is None:
        raise RuntimeError(f"DATABASE_URL_OWNER is not set. Migrations run as {OWNER_ROLE}.")
    return owner_url.get_secret_value()


def _migrate(connection: Connection) -> None:
    # Tables created by the wrong role would be owned by it and sit outside the RLS design.
    current_user = connection.execute(text("select current_user")).scalar_one()
    if current_user != OWNER_ROLE:
        raise RuntimeError(f"Migrations must run as {OWNER_ROLE}, not {current_user}.")
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def _run_online() -> None:
    engine = create_async_engine(_database_url())
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_migrate)
            await connection.commit()
    finally:
        await engine.dispose()


if context.is_offline_mode():
    raise RuntimeError(
        "Offline migrations are not supported: the role check needs a live connection."
    )

asyncio.run(_run_online())
