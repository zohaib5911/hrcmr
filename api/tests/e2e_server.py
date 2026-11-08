"""The API for the browser tests: ``uv run python -m tests.e2e_server`` (started by Playwright).

It gets its own throwaway database (migrated, with the app roles), random secrets, and sends every
e-mail straight to Mailpit. A real ARQ report worker shares its isolated database and Redis.
Everything it creates is dropped when it stops.
The local Postgres, Redis, Mailpit, RustFS and ClamAV test services must be running.
"""

from __future__ import annotations

import asyncio
import os
import secrets
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import uvicorn
from arq.worker import Worker
from fastapi import Body, FastAPI
from redis import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.core.crypto import KeyRing, set_keyring
from app.core.logging import configure_logging
from app.integrations.email import Message, SmtpTransport
from app.jobs.audit import JobAudit
from app.jobs.queue import open_queue
from app.jobs.scheduled import functions
from app.main import create_app
from app.modules.email.outbox import sender_of
from app.modules.email.templates import render
from app.modules.learning.loader import load_courses
from app.modules.soc.importer import load_soc_source
from app.modules.soc.source import load_source
from app.modules.soc_rules.importer import import_rules_source, publish_rules_version
from app.modules.soc_rules.source import PAGE_KINDS, load_rules_source
from tests.db.support import engine_for, temporary_database
from tests.reporting_calendar import seed_reporting_calendar
from tests.support import build_settings

API_PORT = int(os.environ.get("E2E_API_PORT", "8100"))
WEB_ORIGIN = os.environ.get("E2E_WEB_ORIGIN", "http://127.0.0.1:3100")
REDIS_URL = os.environ.get("E2E_REDIS_URL", "redis://127.0.0.1:6379/12")
SMTP_HOST = os.environ.get("E2E_SMTP_HOST", "127.0.0.1")
SMTP_PORT = int(os.environ.get("E2E_SMTP_PORT", "1025"))
S3_SECRET = os.environ.get("RUSTFS_SECRET_KEY", "rustfsadmin")
ROOT = Path(__file__).resolve().parents[2]
RULES_PAGES = ROOT / "data" / "raw" / "rules"  # the saved GOV.UK pages (T15.2)
SOC_FIXTURES = Path(__file__).parent / "fixtures" / "soc"


class DirectMailer:
    """Renders a template and hands it straight to Mailpit (the real path goes through the outbox)."""

    def __init__(self, transport: SmtpTransport, settings: Settings) -> None:
        self._transport = transport
        self._settings = settings

    async def send_template(self, *, to: str, template: str, data: dict[str, str]) -> None:
        rendered = render(template, data, self._settings)
        await self._transport.send(
            Message(
                to=to,
                subject=rendered.subject,
                html=rendered.html,
                plain=rendered.plain,
                sender=sender_of(self._settings),
            )
        )


async def _calendar(owner_url: str) -> None:
    engine = engine_for(owner_url, poolclass=NullPool)
    try:
        await seed_reporting_calendar(engine)
    finally:
        await engine.dispose()


async def _courses(owner_url: str) -> None:
    """The one test course the learning player tests use (never shipped content)."""
    engine = engine_for(owner_url, poolclass=NullPool)
    try:
        async with AsyncSession(engine) as db:
            await load_courses(db, Path(__file__).parent / "fixtures" / "courses")
            await db.commit()
    finally:
        await engine.dispose()


def _fake_embed(texts: Sequence[str]) -> list[list[float]]:
    """The browser tests never download the embedding model: the search uses this instead."""
    return [[1.0 + float((len(text) + dim) % 7) for dim in range(384)] for text in texts]


async def _soc_reference(owner_url: str) -> None:
    """The SOC sample and the saved GOV.UK rules, published, so the sponsorship checker has data."""
    engine = engine_for(owner_url, poolclass=NullPool)
    try:
        async with AsyncSession(engine) as db:
            source = load_source(
                SOC_FIXTURES / "soc2020-coding-index-sample.xlsx",
                SOC_FIXTURES / "soc2020-unit-groups-sample.xlsx",
            )
            await load_soc_source(db, source, _fake_embed)
            rules = load_rules_source(
                {
                    kind: (
                        RULES_PAGES / f"appendix-{kind}-2026-10-29.html",
                        RULES_PAGES / f"appendix-{kind}-2026-10-29.json",
                    )
                    for kind in PAGE_KINDS
                }
            )
            result = await import_rules_source(db, rules)
            assert result.version_id is not None
            await publish_rules_version(db, result.version_id)
            await db.commit()
    finally:
        await engine.dispose()


def _plan_route(app: FastAPI, owner_url: str) -> None:
    """Test-only: put the company of the account with this e-mail on a paid plan, as Stripe's webhook
    would. A new sign-up is on the free plan, which is read-only (T16.2); the browser tests that write
    use a paid account (web/tests/support/accounts.ts), and the free-plan tests keep a free one."""

    async def paid_plan(email: str = Body(embed=True)) -> dict[str, int]:
        engine = engine_for(owner_url, poolclass=NullPool)
        try:
            async with engine.begin() as c:
                changed = await c.execute(
                    text(
                        "update companies set plan = 'annual', subscription_status = 'active' "
                        "where id in (select m.company_id from memberships m "
                        "join users u on u.id = m.user_id where u.email = :e)"
                    ),
                    {"e": email},
                )
        finally:
            await engine.dispose()
        return {"companies": changed.rowcount}

    app.add_api_route("/api/v1/e2e/paid-plan", paid_plan, methods=["POST"])


def main() -> None:
    configure_logging()
    with temporary_database() as database:
        asyncio.run(_calendar(database.owner_url))
        asyncio.run(_courses(database.owner_url))
        asyncio.run(_soc_reference(database.owner_url))
        settings = build_settings(
            database_url=database.app_url,
            redis_url=REDIS_URL,
            web_origin=WEB_ORIGIN,
            api_origin=f"http://127.0.0.1:{API_PORT}",
            domain="127.0.0.1",
            r2_endpoint=os.environ.get("TEST_S3_ENDPOINT", "http://localhost:9000"),
            r2_access_key_id=os.environ.get("RUSTFS_ACCESS_KEY", "rustfsadmin"),
            r2_secret_access_key=S3_SECRET,
            r2_bucket_files=os.environ.get("TEST_S3_BUCKET", "files-dev"),
            clamav_host="localhost",
            clamav_port=int(os.environ.get("TEST_CLAMAV_PORT", "3310")),
            # The test browser is the proxy: a helper sends X-Real-IP so each sign-up looks like a
            # different visitor and the real limit (5 sign-ups an hour per address) stays in force.
            trusted_proxy_cidrs="127.0.0.0/8",
        )
        Redis.from_url(REDIS_URL).flushdb()
        set_keyring(
            KeyRing(
                keys={"k1": secrets.token_bytes(32)},
                active_kid="k1",
                blind_key=secrets.token_bytes(32),
            )
        )
        app = create_app(
            settings, mailer=DirectMailer(SmtpTransport(SMTP_HOST, SMTP_PORT), settings)
        )
        app.state.soc_embedder = _fake_embed
        _plan_route(app, database.owner_url)
        original_lifespan = app.router.lifespan_context

        @asynccontextmanager
        async def with_report_worker(app: FastAPI) -> AsyncIterator[None]:
            async with original_lifespan(app):
                owner = engine_for(database.owner_url, poolclass=NullPool)
                queue = await open_queue(settings)
                worker = Worker(
                    functions=[
                        function for function in functions() if function.name == "generate_report"
                    ],
                    redis_pool=queue._pool,
                    handle_signals=False,
                    poll_delay=0.05,
                    ctx={
                        "engine": app.state.engine,
                        "owner_engine": owner,
                        "storage": app.state.files.storage,
                        "audit": JobAudit(owner),
                    },
                )
                task = asyncio.create_task(worker.async_run())
                try:
                    yield
                finally:
                    with suppress(asyncio.CancelledError):
                        await worker.close()
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
                    await queue.close()
                    await owner.dispose()

        app.router.lifespan_context = with_report_worker
        uvicorn.run(app, host="127.0.0.1", port=API_PORT, log_level="warning")


if __name__ == "__main__":
    main()
