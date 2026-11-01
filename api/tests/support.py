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
        "blind_index_key": random_secret(32),
    }
    values.update(overrides)
    values = {k: v for k, v in values.items() if v is not None}
    return Settings(_env_file=None, **values)
