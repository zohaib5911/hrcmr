from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pydantic import BaseModel

from app.core.config import Settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError, PlanRequiredError
from app.main import create_app
from tests.support import build_settings
from tests.test_config import DEPLOYED_EXTRAS


class Item(BaseModel):
    quantity: int
    email: str


def make_app(settings: Settings | None = None) -> FastAPI:
    app = create_app(settings or build_settings())

    @app.get("/test/not-found")
    async def not_found() -> None:
        raise NotFoundError

    @app.get("/test/forbidden")
    async def forbidden() -> None:
        raise ForbiddenError

    @app.get("/test/conflict")
    async def conflict() -> None:
        raise ConflictError("That employee number is already in use.", field="employee_number")

    @app.get("/test/plan")
    async def plan() -> None:
        raise PlanRequiredError

    @app.get("/test/boom")
    async def boom() -> None:
        raise RuntimeError("internal detail: SECRET-STACK-DETAIL postgresql://u:pw@h/db")

    @app.post("/test/items")
    async def create_item(item: Item) -> Item:
        return item

    @app.get("/test/number/{value}")
    async def number(value: int) -> dict[str, int]:
        return {"value": value}

    return app


@pytest.fixture
async def client(capsys: pytest.CaptureFixture[str]) -> AsyncIterator[httpx.AsyncClient]:
    app = make_app()
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            capsys.readouterr()
            # Like a browser that already has its CSRF cookie and sends the matching header.
            http.cookies.set("csrf", "a-test-csrf-token")
            http.headers["X-CSRF-Token"] = "a-test-csrf-token"
            yield http


def error_of(response: httpx.Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()
    assert list(body) == ["error"]
    error: dict[str, Any] = body["error"]
    assert error["request_id"] == response.headers["x-request-id"]
    return error


async def test_app_error_becomes_the_envelope(client: httpx.AsyncClient) -> None:
    response = await client.get("/test/not-found")
    assert response.status_code == 404
    error = error_of(response)
    assert error["code"] == "NOT_FOUND"
    assert error["message"] == "We could not find that."
    assert "field" not in error


@pytest.mark.parametrize(
    ("path", "status", "code"),
    [("/test/forbidden", 403, "FORBIDDEN"), ("/test/plan", 402, "PLAN_REQUIRED")],
)
async def test_standard_error_codes(
    client: httpx.AsyncClient, path: str, status: int, code: str
) -> None:
    response = await client.get(path)
    assert response.status_code == status
    assert error_of(response)["code"] == code


async def test_field_is_included_when_the_error_is_about_one_input(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/test/conflict")
    assert response.status_code == 409
    error = error_of(response)
    assert error["code"] == "CONFLICT"
    assert error["field"] == "employee_number"


async def test_unknown_path_is_a_404_envelope(client: httpx.AsyncClient) -> None:
    response = await client.get("/nope")
    assert response.status_code == 404
    assert error_of(response)["code"] == "NOT_FOUND"


async def test_wrong_method_is_a_405_envelope_with_allow_header(client: httpx.AsyncClient) -> None:
    response = await client.delete("/test/items")
    assert response.status_code == 405
    assert error_of(response)["code"] == "METHOD_NOT_ALLOWED"
    assert "POST" in response.headers["allow"]


async def test_validation_error_names_the_field_and_never_echoes_the_value(
    client: httpx.AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    response = await client.post(
        "/test/items", json={"quantity": "hunter2-not-a-number", "email": "a@b.c"}
    )
    assert response.status_code == 422
    error = error_of(response)
    assert error["code"] == "VALIDATION_ERROR"
    assert error["field"] == "quantity"
    assert "hunter2" not in response.text
    assert "hunter2" not in capsys.readouterr().out


async def test_validation_error_with_several_problems_mentions_the_rest(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/test/items", json={})
    error = error_of(response)
    assert error["code"] == "VALIDATION_ERROR"
    assert error["field"] == "quantity"
    assert "1 more problem to fix" in error["message"]


async def test_path_parameter_error_uses_the_parameter_name(client: httpx.AsyncClient) -> None:
    response = await client.get("/test/number/abc")
    assert response.status_code == 422
    assert error_of(response)["field"] == "value"


async def test_unhandled_exception_is_a_safe_500(
    client: httpx.AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    response = await client.get("/test/boom")
    assert response.status_code == 500
    error = error_of(response)
    assert error["code"] == "INTERNAL_ERROR"
    assert "quote the request id" in error["message"]
    # Nothing about the cause reaches the caller.
    assert "SECRET-STACK-DETAIL" not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text

    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    crash = next(r for r in records if r["event"] == "unhandled_exception")
    assert crash["request_id"] == error["request_id"]
    assert "RuntimeError" in crash["exception"]  # the operator sees it...
    assert "SECRET-STACK-DETAIL" in crash["exception"]
    assert ":pw@" not in crash["exception"]  # ...but URL credentials are masked
    access = next(r for r in records if r["event"] == "http_request")
    assert access["status"] == 500
    assert access["level"] == "error"


async def test_a_request_id_is_generated_and_returned(client: httpx.AsyncClient) -> None:
    first = await client.get("/api/v1/health")
    second = await client.get("/api/v1/health")
    assert re.fullmatch(r"[0-9a-f]{32}", first.headers["x-request-id"])
    assert first.headers["x-request-id"] != second.headers["x-request-id"]


async def test_a_sensible_caller_request_id_is_kept(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health", headers={"X-Request-ID": "trace-2026.11_01-abc"})
    assert response.headers["x-request-id"] == "trace-2026.11_01-abc"


@pytest.mark.parametrize(
    "bad", ["short", "has spaces in it 12345", "x" * 65, "semi;colon-1234", "a\tb-12345678"]
)
async def test_an_unsafe_caller_request_id_is_replaced(client: httpx.AsyncClient, bad: str) -> None:
    response = await client.get("/api/v1/health", headers={"X-Request-ID": bad})
    assert response.headers["x-request-id"] != bad
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])


async def test_access_log_has_the_request_id_and_never_the_query_string(
    client: httpx.AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    response = await client.get("/test/number/7?token=QUERY-TOKEN-VALUE&email=a@b.c")
    out = capsys.readouterr().out
    assert "QUERY-TOKEN-VALUE" not in out
    assert "a@b.c" not in out
    (record,) = [json.loads(line) for line in out.splitlines()]
    assert record["event"] == "http_request"
    assert record["request_id"] == response.headers["x-request-id"]
    assert record["method"] == "GET"
    assert record["path"] == "/test/number/7"
    assert record["status"] == 200
    assert isinstance(record["duration_ms"], float)


async def test_health_checks_are_not_logged_at_info(
    client: httpx.AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    await client.get("/api/v1/health")
    assert capsys.readouterr().out == ""


async def test_error_responses_are_logged(
    client: httpx.AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    await client.get("/api/v1/health")  # quiet
    await client.get("/nope")
    (record,) = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert record["status"] == 404
    assert record["level"] == "info"


async def test_docs_are_served_locally() -> None:
    app = make_app(build_settings(app_env="local"))
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            assert (await http.get("/api/v1/openapi.json")).status_code == 200
            assert (await http.get("/api/v1/docs")).status_code == 200


@pytest.mark.parametrize("env", ["staging", "production"])
async def test_docs_and_openapi_are_not_served_when_deployed(env: str) -> None:
    app = make_app(build_settings(app_env=env, **DEPLOYED_EXTRAS))
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            for path in (
                "/api/v1/openapi.json",
                "/api/v1/docs",
                "/docs",
                "/openapi.json",
                "/redoc",
            ):
                response = await http.get(path)
                assert response.status_code == 404, path
                assert error_of(response)["code"] == "NOT_FOUND"


async def test_cors_allows_only_our_own_origins_with_credentials(
    client: httpx.AsyncClient,
) -> None:
    ours = build_settings().web_origin
    allowed = await client.options(
        "/test/items",
        headers={
            "Origin": ours,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-csrf-token",
        },
    )
    assert allowed.headers["access-control-allow-origin"] == ours
    assert allowed.headers["access-control-allow-credentials"] == "true"
    assert "x-csrf-token" in allowed.headers["access-control-allow-headers"].lower()

    for origin in ("https://evil.example", "null"):
        refused = await client.options(
            "/test/items",
            headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
        )
        assert "access-control-allow-origin" not in refused.headers
    assert allowed.headers["access-control-allow-origin"] != "*"
