from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI

from app.main import create_app
from app.modules.health.service import run_probes
from tests.support import build_settings


async def test_health_is_alive_without_any_dependency() -> None:
    # Dependencies point at closed ports: liveness must not care.
    app = create_app(
        build_settings(
            database_url="postgresql+asyncpg://u:p@127.0.0.1:1/x", redis_url="redis://127.0.0.1:1/0"
        )
    )
    async with (
        LifespanManager(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as http,
    ):
        response = await http.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.integration
@pytest.mark.usefixtures("stack")
async def test_ready_when_database_and_redis_answer() -> None:
    app = create_app(build_settings())
    async with (
        LifespanManager(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as http,
    ):
        response = await http.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok", "redis": "ok"}}
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.integration
@pytest.mark.usefixtures("stack")
async def test_not_ready_when_the_database_is_down() -> None:
    app = create_app(build_settings(database_url="postgresql+asyncpg://u:p@127.0.0.1:1/x"))
    async with (
        LifespanManager(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as http,
    ):
        response = await http.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "checks": {"database": "fail", "redis": "ok"}}


@pytest.mark.integration
@pytest.mark.usefixtures("stack")
async def test_not_ready_when_redis_is_down() -> None:
    app = create_app(build_settings(redis_url="redis://127.0.0.1:1/0"))
    async with (
        LifespanManager(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as http,
    ):
        response = await http.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "checks": {"database": "ok", "redis": "fail"}}


async def test_ready_response_reveals_nothing_about_the_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = create_app(
        build_settings(
            database_url="postgresql+asyncpg://dbuser:DBPASSWORD-SENTINEL@127.0.0.1:1/secretdb",
            redis_url="redis://:REDISPASSWORD-SENTINEL@127.0.0.1:1/0",
        )
    )
    async with (
        LifespanManager(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as http,
    ):
        response = await http.get("/api/v1/ready")
    assert response.status_code == 503
    for forbidden in ("SENTINEL", "dbuser", "secretdb", "127.0.0.1", "Connect", "asyncpg"):
        assert forbidden not in response.text
    logged = capsys.readouterr().out
    assert "SENTINEL" not in logged
    records = [json.loads(line) for line in logged.splitlines()]
    failures = [r for r in records if r["event"] == "readiness_check_failed"]
    assert {r["check"] for r in failures} == {"database", "redis"}
    assert all("error_type" in r and "message" not in r for r in failures)


async def test_a_slow_dependency_fails_fast_instead_of_hanging() -> None:
    async def slow() -> None:
        await asyncio.sleep(5)

    async def fine() -> None:
        return None

    started = asyncio.get_running_loop().time()
    result = await run_probes({"slow": slow, "fine": fine}, seconds=0.05)
    assert result == {"slow": "fail", "fine": "ok"}
    assert asyncio.get_running_loop().time() - started < 1


async def test_probes_run_concurrently() -> None:
    async def wait() -> None:
        await asyncio.sleep(0.2)

    started = asyncio.get_running_loop().time()
    result = await run_probes({"a": wait, "b": wait, "c": wait}, seconds=1)
    assert set(result.values()) == {"ok"}
    assert asyncio.get_running_loop().time() - started < 0.5


def test_openapi_documents_both_endpoints_and_the_503() -> None:
    app: FastAPI = create_app(build_settings())
    schema = app.openapi()
    assert set(schema["paths"]) == {"/api/v1/health", "/api/v1/ready"}
    ready = schema["paths"]["/api/v1/ready"]["get"]["responses"]
    assert {"200", "503"} <= set(ready)
    assert "ReadyResponse" in json.dumps(ready["503"])
