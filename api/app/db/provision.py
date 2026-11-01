"""One-off, idempotent database provisioning (plan.md T0.5 and T23.2).

Runs with SUPERUSER credentials, supplied only on the command line or in the environment of the
person doing the provisioning (never part of the API's settings). It:

1. creates or updates the ``app_owner`` and ``app_user`` login roles (no superuser, no BYPASSRLS);
2. makes ``app_owner`` the owner of the database and its ``public`` schema, and locks out PUBLIC;
3. creates the extensions, which needs superuser because ``vector`` is not a trusted extension;
4. sets safety timeouts on the runtime role.

Passwords are passed to PostgreSQL as quoted literals produced by the server's own ``format()``.
They are never logged, and they cannot be bound as parameters in ``CREATE ROLE``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.db.roles import APP_ROLE, EXTENSIONS, OWNER_ROLE

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

# Stops a runaway query or a forgotten open transaction from holding the database hostage.
APP_ROLE_SETTINGS = {
    "statement_timeout": "60s",
    "idle_in_transaction_session_timeout": "30s",
}


async def _server_side(connection: AsyncConnection, template: str, **values: str) -> None:
    """Build a statement with the server's ``format()`` (``%I`` identifier, ``%L`` literal)."""
    names = list(values)
    arguments = ", ".join(f"CAST(:{name} AS text)" for name in names)
    statement = (
        await connection.execute(
            text(f"select format(:template, {arguments})"), {"template": template, **values}
        )
    ).scalar_one()
    # exec_driver_sql: the generated text may contain ':' or '%', which text() would misread.
    await connection.exec_driver_sql(statement)


async def _upsert_login_role(connection: AsyncConnection, role: str, password: str) -> None:
    exists = (
        await connection.execute(text("select 1 from pg_roles where rolname = :r"), {"r": role})
    ).scalar()
    verb = "ALTER" if exists else "CREATE"
    await _server_side(
        connection,
        f"{verb} ROLE %I WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION "
        "NOBYPASSRLS PASSWORD %L",
        role=role,
        password=password,
    )


def _database_url(url: URL, database: str) -> URL:
    return url.set(database=database)


async def provision_database(
    admin_url: str, *, database: str, owner_password: str, app_password: str
) -> None:
    """Prepare ``database`` (which must already exist) for the application. Safe to re-run."""
    if not owner_password or not app_password:
        raise ValueError("both role passwords are required")
    base = make_url(admin_url)

    cluster = create_async_engine(_database_url(base, "postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with cluster.connect() as connection:
            await _upsert_login_role(connection, OWNER_ROLE, owner_password)
            await _upsert_login_role(connection, APP_ROLE, app_password)
            await _server_side(
                connection, "ALTER DATABASE %I OWNER TO %I", db=database, role=OWNER_ROLE
            )
            await _server_side(connection, "REVOKE ALL ON DATABASE %I FROM PUBLIC", db=database)
            await _server_side(
                connection,
                "GRANT CONNECT ON DATABASE %I TO %I, %I",
                db=database,
                a=OWNER_ROLE,
                b=APP_ROLE,
            )
            for setting, value in APP_ROLE_SETTINGS.items():
                await _server_side(
                    connection,
                    "ALTER ROLE %I SET %I = %L",
                    role=APP_ROLE,
                    setting=setting,
                    value=value,
                )
    finally:
        await cluster.dispose()

    target = create_async_engine(_database_url(base, database), isolation_level="AUTOCOMMIT")
    try:
        async with target.connect() as connection:
            await _server_side(connection, "ALTER SCHEMA public OWNER TO %I", role=OWNER_ROLE)
            await connection.exec_driver_sql("REVOKE ALL ON SCHEMA public FROM PUBLIC")
            await _server_side(connection, "GRANT USAGE ON SCHEMA public TO %I", role=APP_ROLE)
            for extension in EXTENSIONS:
                await _server_side(connection, "CREATE EXTENSION IF NOT EXISTS %I", ext=extension)
    finally:
        await target.dispose()
