"""Expensive password work leaves the API loop responsive."""

import asyncio
import threading

import httpx
import pytest

from app.main import create_app
from app.modules.auth import passwords
from tests.support import build_settings


async def test_health_answers_while_password_hash_is_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = threading.Event()
    release = threading.Event()

    def slow_hash(password: str) -> str:
        started.set()
        assert release.wait(5)
        return "hashed"

    monkeypatch.setattr(passwords, "hash_password", slow_hash)
    task = asyncio.create_task(passwords.hash_password_async("example"))
    try:
        assert await asyncio.to_thread(started.wait, 2)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(build_settings())), base_url="http://t"
        ) as client:
            response = await asyncio.wait_for(client.get("/api/v1/health"), 1)
        assert response.status_code == 200
        assert not task.done()
    finally:
        release.set()
        await task
