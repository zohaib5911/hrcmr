"""The OpenAPI document is the contract the generated TypeScript client is built from, so what it
says about errors and secrets must be true."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from app.cli import main, openapi_document

API_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(openapi_document())
    return document


def operations(schema: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (method, path, op) for path, ops in schema["paths"].items() for method, op in ops.items()
    ]


def test_the_error_envelope_is_documented(schema: dict[str, Any]) -> None:
    schemas = schema["components"]["schemas"]
    assert {"ErrorBody", "ErrorEnvelope"} <= set(schemas)
    body = schemas["ErrorBody"]
    assert set(body["required"]) == {"code", "message", "request_id"}  # `field` is optional
    assert "field" in body["properties"]


def test_fastapis_own_validation_error_shape_is_not_advertised(schema: dict[str, Any]) -> None:
    """This API returns the envelope for a 422, never FastAPI's `{detail: [...]}`."""
    text = json.dumps(schema)
    assert "HTTPValidationError" not in text
    assert "ValidationError" not in text


def test_every_operation_documents_client_and_server_errors(schema: dict[str, Any]) -> None:
    found = operations(schema)
    assert found
    for method, path, op in found:
        responses = op["responses"]
        for status in ("4XX", "5XX"):
            ref = json.dumps(responses[status])
            assert "#/components/schemas/ErrorEnvelope" in ref, f"{method} {path} {status}"


def test_a_validation_error_really_has_the_documented_shape() -> None:
    """The document and the behaviour agree: a 422 body parses as the documented envelope."""
    import httpx
    from asgi_lifespan import LifespanManager

    from app.main import create_app
    from tests.support import build_settings

    async def run() -> dict[str, Any]:
        app = create_app(build_settings())

        @app.get("/test/number/{value}")
        async def number(value: int) -> dict[str, int]:
            return {"value": value}

        async with LifespanManager(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
                response = await client.get("/test/number/abc")
        assert response.status_code == 422
        body: dict[str, Any] = response.json()
        return body

    import asyncio

    body = asyncio.run(run())
    assert list(body) == ["error"]
    assert set(body["error"]) == {"code", "message", "field", "request_id"}


def test_the_document_is_deterministic() -> None:
    assert openapi_document() == openapi_document()
    assert openapi_document().endswith("\n")


def test_export_needs_no_environment_and_leaks_nothing() -> None:
    """Runs in a subprocess with an empty environment, as CI would."""
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "export-openapi"],
        cwd=API_DIR,
        env={"PATH": os.environ.get("PATH", "")},
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    document = json.loads(result.stdout)
    assert "/health" in document["paths"]
    text = result.stdout.lower()
    # Field names such as "password" are part of the contract; connection strings and key prefixes
    # would be a leak.
    for word in (
        "postgresql",
        "redis://",
        "sk_live",
        "sk_test",
        "whsec_",
        "sk-ant-",
        "private key",
    ):
        assert word not in text


def test_export_can_write_a_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "openapi.json"
    assert main(["export-openapi", "--output", str(target)]) == 0
    assert json.loads(target.read_text())["info"]["title"] == "Platform API"
    assert capsys.readouterr().out == ""
    assert main(["export-openapi"]) == 0
    assert capsys.readouterr().out == target.read_text()


def test_paths_are_relative_to_the_server_so_clients_do_not_double_the_prefix(
    schema: dict[str, Any],
) -> None:
    assert schema["servers"] == [{"url": "/api/v1"}]
    assert all(not path.startswith("/api/v1") for path in schema["paths"])


def test_operation_ids_are_readable(schema: dict[str, Any]) -> None:
    ids = [op["operationId"] for _, _, op in operations(schema)]
    assert {"health_health", "health_ready", "auth_login", "auth_signup"} <= set(ids)
    assert len(ids) == len(set(ids))  # unique
    assert all(re.fullmatch(r"[a-z]+(_[a-z0-9]+)+", op_id) for op_id in ids)  # tag_name, no noise


def test_the_served_document_matches_the_exported_one() -> None:
    """`/api/v1/openapi.json` (local only) and `export-openapi` describe the same API."""
    import asyncio

    import httpx
    from asgi_lifespan import LifespanManager

    from app.main import create_app
    from tests.support import build_settings

    async def fetch() -> dict[str, Any]:
        app = create_app(build_settings())
        async with LifespanManager(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
                document: dict[str, Any] = (await client.get("/api/v1/openapi.json")).json()
                return document

    assert asyncio.run(fetch()) == json.loads(openapi_document())
