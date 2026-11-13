"""T21.1: reviewed endpoint inventory and the platform/anonymous sides of the RBAC matrix.

Tenant roles x every permission-bearing endpoint are exercised in test_rbac_enforcement.
Account flows, public reference data and Stripe use their own credentials, not tenant RBAC;
the frozen inventory lists each exception by method/path rather than exempting whole prefixes.
"""

from __future__ import annotations

import json
import uuid
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

import pytest
from fastapi import Request
from fastapi.dependencies.models import Dependant
from fastapi.dependencies.utils import solve_dependencies

from app.core.errors import AppError
from app.core.rbac_matrix import PLATFORM_PERMISSIONS
from app.db.session import GlobalSession
from app.main import create_app
from app.modules.rbac.platform import PlatformAccess
from tests.db.support import engine_for
from tests.db.test_rbac_enforcement import Setup
from tests.db.test_rbac_enforcement import setup as setup
from tests.route_support import permissions, registered_routes
from tests.support import build_settings

INVENTORY = Path(__file__).parents[1] / "fixtures" / "endpoint_permissions.json"
SPECIAL_POLICIES = {"account-flow", "public", "stripe-signature", "health"}


def endpoint_inventory() -> dict[str, list[str]]:
    inventory: dict[str, list[str]] = json.loads(INVENTORY.read_text())
    return inventory


def test_every_endpoint_has_the_reviewed_permission_or_explicit_exception() -> None:
    expected = endpoint_inventory()
    actual = {}
    for path, methods, dependant in registered_routes(create_app(build_settings())):
        required = sorted(permissions(dependant))
        for method in methods:
            key = f"{method} {path}"
            # Only these exact reviewed exceptions can bypass require/require_platform.
            policy = expected.get(key, [])
            actual[key] = required or (policy if set(policy) <= SPECIAL_POLICIES else [])
            assert actual[key], f"No reviewed security policy: {key}"
    assert actual == expected


async def resolve(
    app: Any, dependant: Dependant, path: str, method: str, cookie: str = ""
) -> list[PlatformAccess]:
    """Run the real guard graph, without invoking handlers or mutating business resources."""
    async with AsyncExitStack() as stack:
        request = Request(
            {
                "type": "http",
                "app": app,
                "method": method,
                "path": path,
                "query_string": b"",
                "path_params": {},
                "headers": [(b"cookie", cookie.encode())],
                "client": ("127.0.0.1", 1234),
                "scheme": "http",
                "server": ("test", 80),
                "fastapi_inner_astack": stack,
                "fastapi_function_astack": stack,
            }
        )
        solved = await solve_dependencies(
            request=request,
            dependant=dependant,
            async_exit_stack=stack,
            embed_body_fields=False,
            dependency_overrides_provider=app,
        )
        return [v for v in solved.dependency_cache.values() if isinstance(v, PlatformAccess)]


async def test_anonymous_is_refused_by_every_permission_bearing_endpoint(setup: Setup) -> None:
    app = setup.client._transport.app  # type: ignore[attr-defined]
    checked = set()
    for path, methods, dependant in registered_routes(app):
        if path.startswith("/api/v1/probe/") or not permissions(dependant):
            continue
        for method in methods:
            with pytest.raises(AppError) as raised:
                await resolve(app, dependant, path, method)
            assert (raised.value.status_code, raised.value.code) == (401, "UNAUTHENTICATED"), (
                method,
                path,
            )
            checked.add(f"{method} {path}")
    assert checked == {
        key for key, policy in endpoint_inventory().items() if not set(policy) & SPECIAL_POLICIES
    }


@pytest.mark.parametrize("level", ["support", "owner"])
async def test_every_platform_guard_admits_both_platform_levels(setup: Setup, level: str) -> None:
    """Owner-only actions also have handler checks, covered by test_platform_*.

    Both platform levels pass the shared permission guard; tenant roles and anonymous sessions
    must fail it. Check every method, including course/rule editors outside /platform/.
    """
    app = setup.client._transport.app  # type: ignore[attr-defined]
    async with await setup.person("company_admin") as browser:
        tenant_token = browser.cookies.get("brand_session")
        data = await setup.sessions.get(tenant_token)
        assert data is not None
        await setup.owner(
            "insert into platform_admins (user_id, level) values (:u, :l)",
            u=data.user_id,
            l=level,
        )
        await setup.owner("update users set mfa_enabled=true where id=:u", u=data.user_id)
        engine = engine_for(setup.db.app_url)
        try:
            async with GlobalSession(engine) as db:
                token, _ = await setup.sessions.create(
                    db,
                    user_id=uuid.UUID(data.user_id),
                    company_id=None,
                    ip=None,
                    user_agent=None,
                    mfa_passed=True,
                    platform=True,
                )
                await db.commit()
        finally:
            await engine.dispose()
        checked = set()
        for path, methods, dependant in registered_routes(app):
            required = permissions(dependant)
            if not set(required) & PLATFORM_PERMISSIONS:
                continue
            for method in methods:
                accesses = await resolve(
                    app, dependant, path, method, f"brand_platform_session={token}"
                )
                assert accesses, (level, method, path)
                assert all(str(access.caller.user_id) == data.user_id for access in accesses)
                checked.add(f"{method} {path}")
        assert checked == {
            key
            for key, policy in endpoint_inventory().items()
            if set(policy) & PLATFORM_PERMISSIONS
        }
