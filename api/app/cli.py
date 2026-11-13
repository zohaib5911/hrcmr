"""Operator commands. Run from ``api/`` as ``python -m app.cli <command>``.

provision-db   Create/refresh the app_owner and app_user roles, ownership and extensions.
               Needs a SUPERUSER URL in DATABASE_URL_ADMIN (not part of the API's settings).
migrate        Apply migrations (``alembic upgrade head``) as app_owner.
check-rls      Fail if any tenant table lacks Row-Level Security or an updated_at trigger.
rotate-keys    Re-encrypt every encrypted column with the active key (after adding a new key).
export-openapi Print (or --output) the OpenAPI document.
export-data-model Print (or --output) docs/data-model.md, generated from the models.
email-samples  Send one of every e-mail to the configured mail service (Mailpit on a dev machine).
seed-perf      Development only: add a company "perf-test" with 1,000 employees and their leave
               and attendance, to measure the main lists (T22.2). Refused on staging/production.
load-places    Load a saved ONS Index of Place Names CSV (FILE --version LABEL) for register
               geocoding; later register imports reuse it. See docs/runbooks/register-places.md.
load-companies Load a Companies House monthly bulk CSV (FILE --version LABEL). Matching needs
               REGISTER_BULK_MATCH_ENABLED=true. See docs/runbooks/register-companies.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
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


async def _rotate_keys() -> int:
    from app.db.rotate import rotate_keys

    settings = get_settings()
    if settings.database_url_owner is None:
        raise SystemExit("DATABASE_URL_OWNER is not set. Key rotation must reach every company.")
    engine = create_async_engine(settings.database_url_owner.get_secret_value())
    try:
        changed = await rotate_keys(engine)
    finally:
        await engine.dispose()
    for label, count in changed.items():
        print(f"{label}: {count} re-encrypted")  # noqa: T201
    print("Done. Remove an old key from FIELD_ENCRYPTION_KEYS only after a second run changes 0.")  # noqa: T201
    return 0


async def _email_samples() -> int:
    from app.db.engine import create_engine
    from app.integrations.email import transport_from_settings

    try:
        from seed.email_samples import send_samples
    except ModuleNotFoundError:
        raise SystemExit("email-samples is for development: seed/ is not in this image.") from None

    settings = get_settings()
    transport = transport_from_settings(settings)
    if transport is None:
        raise SystemExit("Set SMTP_HOST (Mailpit) or RESEND_API_KEY first.")
    engine = create_engine(settings)
    try:
        sent = await send_samples(engine, transport, settings)
    finally:
        await engine.dispose()
    print(f"{sent} sample e-mails sent.")  # noqa: T201
    return 0


async def _seed_perf() -> int:
    try:
        from seed.perf import seed_perf_test_company
    except ModuleNotFoundError:
        raise SystemExit("seed-perf is for development: seed/ is not in this image.") from None

    settings = get_settings()
    if settings.app_env.is_deployed:
        raise SystemExit("seed-perf is for development; it never runs on staging or production.")
    if settings.database_url_owner is None:
        raise SystemExit("DATABASE_URL_OWNER is not set.")
    engine = create_async_engine(settings.database_url_owner.get_secret_value())
    try:
        async with engine.begin() as connection:
            count = await seed_perf_test_company(connection)
            if count is None:
                raise SystemExit("Company perf-test already exists; nothing added.")
    finally:
        await engine.dispose()
    print(f"Company perf-test seeded with {count} employees.")  # noqa: T201
    return 0


async def _load_places(content: bytes, source: str, version: str) -> int:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.register.geo import load_place_dataset

    settings = get_settings()
    if settings.database_url_owner is None:
        raise SystemExit("DATABASE_URL_OWNER is not set. Only the owner writes register data.")
    engine = create_async_engine(settings.database_url_owner.get_secret_value())
    try:
        async with AsyncSession(engine) as db:
            try:
                dataset, placed = await load_place_dataset(
                    db, content, version=version, source=source
                )
            except ValueError as error:
                raise SystemExit(f"Refused: {error}") from None
            rows = dataset.row_count
            await db.commit()
    finally:
        await engine.dispose()
    print(f"Loaded {rows} places ({version}); {placed} sponsors placed.")  # noqa: T201
    return 0


async def _load_companies(path: Path, version: str) -> int:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.register.geo import load_company_dataset

    settings = get_settings()
    if settings.database_url_owner is None:
        raise SystemExit("DATABASE_URL_OWNER is not set. Only the owner writes register data.")
    engine = create_async_engine(settings.database_url_owner.get_secret_value())
    try:
        async with AsyncSession(engine) as db:
            try:
                with path.open("rb") as content:  # streamed: never read whole into memory
                    dataset, matched = await load_company_dataset(
                        db,
                        content,
                        version=version,
                        source=path.name,
                        enabled=settings.register_bulk_match_enabled,
                    )
            except ValueError as error:
                raise SystemExit(f"Refused: {error}") from None
            rows = dataset.row_count
            await db.commit()
    finally:
        await engine.dispose()
    print(f"Loaded {rows} company rows ({version}); {matched} sponsors matched.")  # noqa: T201
    return 0


def openapi_document() -> str:
    """The API's OpenAPI document as stable, sorted JSON.

    The app is built with throwaway settings (nothing connects to anything), so this needs no
    environment and can run in CI or on a machine with no secrets. The output contains none of them.
    """
    from pydantic import SecretStr

    from app.core.config import AppEnv, Settings
    from app.main import create_app

    throwaway = secrets.token_urlsafe(32)
    settings = Settings(
        _env_file=None,
        app_env=AppEnv.TEST,
        domain="localhost",
        web_origin="http://localhost:3000",
        admin_origin="http://admin.localhost:3000",
        api_origin="http://localhost:8000",
        database_url=SecretStr("postgresql+asyncpg://openapi@localhost/openapi"),
        redis_url=SecretStr("redis://localhost:6379/0"),
        session_secret=SecretStr(throwaway),
        field_encryption_keys=SecretStr(json.dumps({"k1": throwaway})),
        blind_index_key=SecretStr(throwaway),
    )
    return json.dumps(create_app(settings).openapi(), indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "provision-db",
            "migrate",
            "check-rls",
            "export-openapi",
            "export-data-model",
            "rotate-keys",
            "email-samples",
            "seed-perf",
            "load-places",
            "load-companies",
        ],
    )
    parser.add_argument(
        "file", nargs="?", type=Path, help="load-places/load-companies: saved bulk CSV"
    )
    parser.add_argument("--version", help="load-places/load-companies: dataset edition")
    parser.add_argument(
        "--output", type=Path, help="export-openapi, export-data-model: write to this file"
    )
    args = parser.parse_args(argv)

    if args.command == "provision-db":
        asyncio.run(_provision())
        return 0
    if args.command == "migrate":
        command.upgrade(alembic_config(), "head")
        return 0
    if args.command == "export-openapi":
        document = openapi_document()
        if args.output:
            args.output.write_text(document)
        else:
            sys.stdout.write(document)
        return 0
    if args.command == "rotate-keys":
        return asyncio.run(_rotate_keys())
    if args.command == "load-companies":
        if args.file is None or not args.version or len(args.version) > 100:
            parser.error("load-companies needs FILE and --version (1-100 characters)")
        if not args.file.is_file():
            raise SystemExit(f"{args.file} is not a file. Download the bulk CSV first.")
        return asyncio.run(_load_companies(args.file, args.version))
    if args.command == "load-places":
        if args.file is None or not args.version:
            parser.error("load-places needs FILE and --version")
        if not args.file.is_file():
            raise SystemExit(f"{args.file} is not a file. Download the ONS file first.")
        return asyncio.run(_load_places(args.file.read_bytes(), args.file.name, args.version))
    if args.command == "email-samples":
        return asyncio.run(_email_samples())
    if args.command == "seed-perf":
        return asyncio.run(_seed_perf())
    if args.command == "export-data-model":
        from app.db.data_model import data_model_markdown

        document = data_model_markdown()
        if args.output:
            args.output.write_text(document)
        else:
            sys.stdout.write(document)
        return 0
    return asyncio.run(_check_rls())


if __name__ == "__main__":
    sys.exit(main())
