"""Operator commands. Run from ``api/`` as ``python -m app.cli <command>``.

provision-db   Create/refresh the app_owner and app_user roles, ownership and extensions.
               Needs a SUPERUSER URL in DATABASE_URL_ADMIN (not part of the API's settings).
migrate        Apply migrations (``alembic upgrade head``) as app_owner.
check-rls      Fail if any tenant table lacks Row-Level Security or an updated_at trigger.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from alembic.config import Config
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from app.core.config import get_settings
from app.db.provision import provision_database
from app.db.rls import (
    materialized_views,
    security_definer_functions,
    tables_missing_tenant_rls,
    tables_missing_updated_at_trigger,
    views_bypassing_rls,
)
from app.db.roles import APP_ROLE, OWNER_ROLE

API_DIR = Path(__file__).resolve().parents[1]


def alembic_config(url: str | None = None) -> Config:
    config = Config(str(API_DIR / "alembic.ini"))
    if url:
        config.attributes["url"] = url
    return config


def _role_password(url_value: str, expected_role: str, variable: str) -> tuple[str, str]:
    url = make_url(url_value)
    if url.username != expected_role:
        raise SystemExit(f"{variable} must connect as {expected_role}, not {url.username}.")
    if not url.password or not url.database:
        raise SystemExit(f"{variable} must include a password and a database name.")
    return url.database, url.password


async def _provision() -> None:
    admin_url = os.environ.get("DATABASE_URL_ADMIN")
    if not admin_url:
        raise SystemExit(
            "Set DATABASE_URL_ADMIN to a superuser connection URL for this one-off step."
        )
    settings = get_settings()
    if settings.database_url_owner is None:
        raise SystemExit("DATABASE_URL_OWNER is not set.")
    database, owner_password = _role_password(
        settings.database_url_owner.get_secret_value(), OWNER_ROLE, "DATABASE_URL_OWNER"
    )
    app_database, app_password = _role_password(
        settings.database_url.get_secret_value(), APP_ROLE, "DATABASE_URL"
    )
    if database != app_database:
        raise SystemExit("DATABASE_URL and DATABASE_URL_OWNER must name the same database.")
    await provision_database(
        admin_url, database=database, owner_password=owner_password, app_password=app_password
    )
    print(f"Provisioned {OWNER_ROLE} and {APP_ROLE} on database {database!r}.")  # noqa: T201


async def _check_rls() -> int:
    settings = get_settings()
    # The owner connection can read the catalogs; so can the runtime role.
    url = (settings.database_url_owner or settings.database_url).get_secret_value()
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            problems = {
                "has company_id but no Row-Level Security policy": (
                    await tables_missing_tenant_rls(connection)
                ),
                "has updated_at but no trg_set_updated_at trigger": (
                    await tables_missing_updated_at_trigger(connection)
                ),
                "is a view that bypasses Row-Level Security (use create_tenant_view)": (
                    await views_bypassing_rls(connection)
                ),
                "is a materialised view, which cannot enforce Row-Level Security": (
                    await materialized_views(connection)
                ),
                "is a SECURITY DEFINER function, which bypasses Row-Level Security": (
                    await security_definer_functions(connection)
                ),
            }
    finally:
        await engine.dispose()
    failed = False
    for message, names in problems.items():
        for name in names:
            failed = True
            print(f"FAIL {name}: {message}")  # noqa: T201
    if not failed:
        print("OK: tenant tables, views, and functions all respect Row-Level Security.")  # noqa: T201
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__)
    parser.add_argument("command", choices=["provision-db", "migrate", "check-rls"])
    args = parser.parse_args(argv)

    if args.command == "provision-db":
        asyncio.run(_provision())
        return 0
    if args.command == "migrate":
        command.upgrade(alembic_config(), "head")
        return 0
    return asyncio.run(_check_rls())


if __name__ == "__main__":
    sys.exit(main())
