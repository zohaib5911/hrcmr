"""Shared test helpers: build a valid ``Settings`` with random fake secrets, never from a .env."""

from __future__ import annotations

import base64
import json
import os
import secrets
from typing import Any

from app.core.config import Settings

POSTGRES_TEST_PORT = os.environ.get("POSTGRES_TEST_PORT", "5433")
REDIS_PORT = os.environ.get("REDIS_PORT", "6379")
# Matches the `postgres-test` service in docker-compose.yml (a disposable server, superuser
# access). Override with TEST_DATABASE_URL / TEST_REDIS_URL (CI does).
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or (
    f"postgresql+asyncpg://postgres:{os.environ.get('POSTGRES_PASSWORD', 'postgres')}"
    f"@localhost:{POSTGRES_TEST_PORT}/postgres"
)
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL") or f"redis://localhost:{REDIS_PORT}/15"


def random_secret(nbytes: int = 24) -> str:
    return secrets.token_urlsafe(nbytes)


def build_settings(**overrides: Any) -> Settings:
    """A valid test configuration. Pass field values to override; ``None`` removes a default."""
    values: dict[str, Any] = {
        "app_env": "test",
        "domain": "localhost",
        "web_origin": "http://localhost:3000",
        "admin_origin": "http://admin.localhost:3000",
        "api_origin": "http://localhost:8000",
        "database_url": TEST_DATABASE_URL,
        "redis_url": TEST_REDIS_URL,
        "session_secret": random_secret(48),
        "field_encryption_keys": json.dumps(
            {"k1": base64.b64encode(secrets.token_bytes(32)).decode()}
        ),
        "blind_index_key": base64.b64encode(secrets.token_bytes(32)).decode(),
    }
    values.update(overrides)
    values = {k: v for k, v in values.items() if v is not None}
    return Settings(_env_file=None, **values)


async def step_up(client: Any, cookie: str = "brand_session") -> None:
    """Marks the client's tenant session as just stepped up, as POST /auth/step-up would."""
    from redis.asyncio import Redis

    from app.modules.auth.sessions import SessionStore

    redis = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    try:
        store = SessionStore(redis)
        token = client.cookies.get(cookie)
        data = await store.get(token)
        assert data is not None, "no live session to step up"
        await store.mark_step_up(token, data)
    finally:
        await redis.aclose()


def csrf_ready(client: Any, app: Any) -> Any:
    """Gives a test client what the web app has (C6.1.6): a CSRF token signed for the session
    cookies it holds now, and before every request the current ``csrf`` cookie copied into the
    ``X-CSRF-Token`` header. When a response renews the token (sign-in, sign-out), the next request
    uses the new one, as in a browser. Call it after setting the client's session cookies."""
    from app.core.csrf import CSRF_COOKIE, CSRF_HEADER, new_csrf_token

    settings = app.state.settings
    names = (
        settings.session_cookie_name,
        settings.platform_session_cookie_name,
        settings.support_session_cookie_name,
    )
    held = {cookie.name: cookie.value for cookie in client.cookies.jar}
    token = new_csrf_token(
        settings.session_secret.get_secret_value().encode(), tuple(held.get(n) for n in names)
    )
    # The domain the server's own Set-Cookie gets, so a renewed token replaces this one.
    host = client.base_url.host
    client.cookies.set(CSRF_COOKIE, token, domain=host if "." in host else f"{host}.local")

    async def copy_token(request: Any) -> None:
        current = [cookie.value for cookie in client.cookies.jar if cookie.name == CSRF_COOKIE]
        if current:
            request.headers[CSRF_HEADER] = current[-1]

    client.event_hooks["request"].append(copy_token)
    return client
