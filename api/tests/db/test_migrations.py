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
# The identity migration (T2.1) adds these tables and these two functions.
IDENTITY_TABLES = [
    "attendance_imports",
    "attendance_records",
    "audit_events",
    "bank_holidays",
    "change_of_circumstances",
    "companies",
    "company_bank_accounts",
    "company_compliance_documents",
    "company_holidays",
    "departments",
    "designations",
    "dossier_links",
    "email_outbox",
    "email_tokens",
    "emergency_contacts",
    "employee_addresses",
    "employee_assignments",
    "employee_bank_details",
    "employee_compensation",
    "employee_documents",
    "employee_education",
    "employee_memberships",
    "employee_previous_employment",
    "employee_responsibilities",
    "employee_training_records",
    "employees",
    "files",
    "holiday_types",
    "invitations",
    "key_persons",
    "leave_ledger",
    "leave_requests",
    "leave_types",
    "leave_year_end_runs",
    "locations",
    "memberships",
    "notifications",
    "org_changes",
    "pay_bands",
    "pay_schedules",
    "payment_types",
    "platform_admins",
    "reminders",
    "rtw_checks",
    "sessions",
    "sponsor_documents",
    "tax_codes",
    "terms_acceptances",
    "terms_versions",
    "trading_hours_days",
    "users",
    "working_pattern_days",
]
IDENTITY_FUNCTIONS = {
    "app_current_user_id",
    "audit_events_append_only",
    "rtw_checks_immutable",
    "sponsor_documents_immutable",
    "compliance_changes_immutable",
    "reminders_immutable",
    "leave_ledger_immutable",
    "leave_year_end_immutable",
}


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


def _tables(url: str) -> list[str]:
    sql = (
        "select table_name from information_schema.tables where table_schema = 'public' "
        "and table_name <> 'alembic_version' and table_type = 'BASE TABLE'"
    )
    return asyncio.run(_query(url, sql))


def _all_functions(url: str) -> set[str]:
    sql = (
        "select p.proname from pg_proc p join pg_namespace n on n.oid = p.pronamespace "
        "where n.nspname = 'public' and not exists "
        "(select 1 from pg_depend d where d.objid = p.oid and d.deptype = 'e')"
    )
    return set(asyncio.run(_query(url, sql)))


def test_migrations_apply_roll_back_and_apply_again_cleanly() -> None:
    with temporary_database(migrate=False) as db:
        config = alembic_config(db.owner_url)
        assert _functions(db.owner_url) == set()

        command.upgrade(config, "head")
        assert _functions(db.owner_url) == FUNCTIONS
        head = ScriptDirectory.from_config(config).get_current_head()
        assert asyncio.run(_query(db.owner_url, "select version_num from alembic_version")) == [
            head
        ]
        assert _tables(db.owner_url) == IDENTITY_TABLES
        assert _all_functions(db.owner_url) == FUNCTIONS | IDENTITY_FUNCTIONS

        command.downgrade(config, "0001_foundations")
        assert _tables(db.owner_url) == []
        assert _all_functions(db.owner_url) == FUNCTIONS

        command.downgrade(config, "base")
        assert _functions(db.owner_url) == set()
        assert _all_functions(db.owner_url) == set()

        command.upgrade(config, "head")
        assert _functions(db.owner_url) == FUNCTIONS
        assert _tables(db.owner_url) == IDENTITY_TABLES


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


def test_leave_defaults_backfill_existing_companies_without_changing_settings() -> None:
    async def seed(url: str) -> None:
        engine = engine_for(url, poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "insert into companies (name,slug,leave_year_start_month_day,allow_negative_leave_balance) values ('Existing','existing','04-06',true)"
                    )
                )
        finally:
            await engine.dispose()

    async def verify(url: str) -> None:
        engine = engine_for(url, poolclass=NullPool)
        try:
            async with engine.connect() as connection:
                rows = (
                    await connection.execute(
                        text("select name,source_url,checked_on from leave_types")
                    )
                ).all()
                assert len(rows) == 12
                assert all(
                    str(row[1]).startswith("https://www.gov.uk/") and str(row[2]) == "2026-11-03"
                    for row in rows
                )
                assert (
                    await connection.execute(
                        text(
                            "select leave_year_start_month_day,allow_negative_leave_balance from companies"
                        )
                    )
                ).one() == ("04-06", True)
        finally:
            await engine.dispose()

    with temporary_database(migrate=False) as db:
        config = alembic_config(db.owner_url)
        command.upgrade(config, "0020_auth_audit")
        asyncio.run(seed(db.owner_url))
        command.upgrade(config, "head")
        asyncio.run(verify(db.owner_url))
