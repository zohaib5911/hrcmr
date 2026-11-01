"""Database engine factory. The tenant session, RLS helpers and models build on this later."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

if TYPE_CHECKING:
    from app.core.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        # Keeps bound parameter values (which can be personal data) out of error messages and logs.
        hide_parameters=True,
        connect_args={"timeout": 5, "server_settings": {"application_name": "brand-api"}},
    )


async def ping_database(engine: AsyncEngine) -> None:
    """Raise if the database does not answer a trivial query."""
    async with engine.connect() as connection:
        await connection.execute(text("select 1"))
