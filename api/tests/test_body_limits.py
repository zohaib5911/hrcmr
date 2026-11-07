"""Every route that takes a file gets a body limit above the 1 MB default (AUDIT-1 C1.2.3).

The middleware refuses a body before the endpoint sees it, so a route missing from its table could
never receive a file over 1 MB, whatever the endpoint's own size check says.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, cast

from app.core.body_limit import DEFAULT_LIMIT, BodyLimitMiddleware
from app.main import API_PREFIX, create_app
from tests.support import build_settings

PARAM = re.compile(r"\{[^}]+\}")


def _middleware() -> tuple[BodyLimitMiddleware, dict[str, Any]]:
    app = create_app(build_settings())
    for item in app.user_middleware:
        factory: object = item.cls
        if factory is BodyLimitMiddleware:
            limits = cast("dict[str | re.Pattern[str], int]", item.kwargs["limits"])
            return BodyLimitMiddleware(app, limits=limits), app.openapi()
    raise AssertionError("BodyLimitMiddleware is not installed")


def _upload_paths(schema: dict[str, Any]) -> list[str]:
    found = []
    for path, operations in schema["paths"].items():
        for operation in operations.values():
            content = operation.get("requestBody", {}).get("content", {})
            if "multipart/form-data" in content:
                found.append(API_PREFIX + PARAM.sub(str(uuid.uuid4()), path))
    return found


def test_every_upload_route_takes_more_than_the_default() -> None:
    limiter, schema = _middleware()
    uploads = _upload_paths(schema)
    assert len(uploads) >= 11
    small = [path for path in uploads if limiter._limit_for(path) <= DEFAULT_LIMIT]
    assert small == []


def test_json_routes_beside_uploads_keep_the_default() -> None:
    limiter, _schema = _middleware()
    some = uuid.uuid4()
    for path in (
        f"{API_PREFIX}/policies",
        f"{API_PREFIX}/policies/{some}/send",
        f"{API_PREFIX}/employees",
        f"{API_PREFIX}/employees/{some}",
        f"{API_PREFIX}/documents/{some}",
    ):
        assert limiter._limit_for(path) == DEFAULT_LIMIT, path
