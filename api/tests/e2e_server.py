"""The API for the browser tests: ``uv run python -m tests.e2e_server`` (started by Playwright).

It gets its own throwaway database (migrated, with the app roles), random secrets, and sends every
e-mail straight to Mailpit, so no worker has to run. Everything it creates is dropped when it stops.
The local Postgres, Redis, Mailpit, RustFS and ClamAV test services must be running.
"""

from __future__ import annotations

import asyncio
import os
import secrets

import uvicorn
from redis import Redis
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.core.crypto import KeyRing, set_keyring
from app.core.logging import configure_logging
from app.integrations.email import Message, SmtpTransport
from app.main import create_app
from app.modules.email.outbox import sender_of
from app.modules.email.templates import render
from tests.db.support import engine_for, temporary_database
from tests.reporting_calendar import seed_reporting_calendar
from tests.support import build_settings

API_PORT = int(os.environ.get("E2E_API_PORT", "8100"))
WEB_ORIGIN = os.environ.get("E2E_WEB_ORIGIN", "http://127.0.0.1:3100")
REDIS_URL = os.environ.get("E2E_REDIS_URL", "redis://127.0.0.1:6379/12")
SMTP_HOST = os.environ.get("E2E_SMTP_HOST", "127.0.0.1")
SMTP_PORT = int(os.environ.get("E2E_SMTP_PORT", "1025"))
S3_SECRET = os.environ.get("RUSTFS_SECRET_KEY", "rustfsadmin")


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


def main() -> None:
    configure_logging()
    with temporary_database() as database:
        asyncio.run(_calendar(database.owner_url))
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
        uvicorn.run(app, host="127.0.0.1", port=API_PORT, log_level="warning")


if __name__ == "__main__":
    main()
