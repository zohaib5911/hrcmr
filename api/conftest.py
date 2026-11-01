from __future__ import annotations

import socket
from urllib.parse import urlsplit

import pytest

from app.core.config import Settings
from tests.support import TEST_DATABASE_URL, TEST_REDIS_URL


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing from the developer's shell may leak into a test."""
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


def _reachable(url: str) -> bool:
    parts = urlsplit(url.replace("+asyncpg", ""))
    try:
        with socket.create_connection((parts.hostname or "localhost", parts.port or 0), timeout=2):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def stack() -> None:
    """Integration tests need Postgres and Redis. Fail loudly (never skip) when they are down."""
    services = (("Postgres", TEST_DATABASE_URL), ("Redis", TEST_REDIS_URL))
    down = [name for name, url in services if not _reachable(url)]
    if down:
        names = " and ".join(down)
        pytest.fail(f"{names} not reachable. Start the local stack: docker compose up -d --wait")
