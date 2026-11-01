from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from app.cli import main
from app.db.rls import tenant_rls_statements, updated_at_trigger_statements
from tests.db.support import engine_for, settings_environment, temporary_database


def test_provision_migrate_and_check_work_end_to_end(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with temporary_database(provision=False) as db:
        settings_environment(monkeypatch, db)
        assert main(["provision-db"]) == 0
        assert main(["migrate"]) == 0
        capsys.readouterr()
        assert main(["check-rls"]) == 0
        assert "OK:" in capsys.readouterr().out
        # No password reaches the output.
        assert db.app_password not in capsys.readouterr().out


def test_check_rls_fails_for_a_tenant_table_without_a_policy(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with temporary_database() as db:
        settings_environment(monkeypatch, db)

        async def create_table(*extra: str) -> None:
            engine = engine_for(db.owner_url, poolclass=NullPool)
            try:
                async with engine.begin() as connection:
                    for statement in extra:
                        await connection.execute(text(statement))
            finally:
                await engine.dispose()

        asyncio.run(
            create_table(
                "create table forgetful (id uuid primary key, company_id uuid not null, "
                "updated_at timestamptz not null default now())"
            )
        )
        capsys.readouterr()
        assert main(["check-rls"]) == 1
        output = capsys.readouterr().out
        assert "FAIL forgetful: has company_id but no Row-Level Security policy" in output
        assert "FAIL forgetful: has updated_at but no trg_set_updated_at trigger" in output

        asyncio.run(
            create_table(
                *tenant_rls_statements("forgetful"), *updated_at_trigger_statements("forgetful")
            )
        )
        assert main(["check-rls"]) == 0


def test_provision_needs_the_admin_url(monkeypatch: pytest.MonkeyPatch) -> None:
    with temporary_database(provision=False) as db:
        settings_environment(monkeypatch, db)
        monkeypatch.delenv("DATABASE_URL_ADMIN")
        with pytest.raises(SystemExit, match="DATABASE_URL_ADMIN"):
            main(["provision-db"])


def test_provision_refuses_urls_that_use_the_wrong_role(monkeypatch: pytest.MonkeyPatch) -> None:
    with temporary_database(provision=False) as db:
        settings_environment(monkeypatch, db)
        monkeypatch.setenv("DATABASE_URL", db.admin_url)  # the postgres superuser, not app_user
        from app.core.config import get_settings

        get_settings.cache_clear()
        with pytest.raises(SystemExit, match="must connect as app_user"):
            main(["provision-db"])
