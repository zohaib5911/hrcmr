from __future__ import annotations

import asyncio

import httpx
import pytest
from asgi_lifespan import LifespanManager
from fastapi import Request
from sqlalchemy import select

from app.db.session import GlobalDb, TenantDb
from app.main import create_app
from tests.db.support import DatabaseUnderTest
from tests.db.test_tenant_session import COMPANY_A, COMPANY_B, Widget, _prepare
from tests.support import build_settings


@pytest.fixture
def seeded(database: DatabaseUnderTest) -> DatabaseUnderTest:
    asyncio.run(_prepare(database))
    return database


async def test_the_tenant_dependency_refuses_a_request_with_no_company(
    seeded: DatabaseUnderTest,
) -> None:
    app = create_app(build_settings(database_url=seeded.app_url))

    @app.get("/test/widgets")
    async def widgets(db: TenantDb) -> list[str]:
        return [w.name for w in (await db.execute(select(Widget))).scalars()]

    async with (
        LifespanManager(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as http,
    ):
        response = await http.get("/test/widgets")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_the_tenant_dependency_scopes_to_the_company_on_the_request(
    seeded: DatabaseUnderTest,
) -> None:
    app = create_app(build_settings(database_url=seeded.app_url))

    @app.middleware("http")
    async def pretend_to_be_signed_in(request: Request, call_next):  # type: ignore[no-untyped-def]
        company = request.headers.get("x-test-company")
        if company:
            request.state.company_id = company  # a string, as an auth layer might store it
        return await call_next(request)

    @app.get("/test/widgets")
    async def widgets(db: TenantDb) -> list[str]:
        return sorted(w.name for w in (await db.execute(select(Widget))).scalars())

    @app.get("/test/global")
    async def global_view(db: GlobalDb) -> list[str]:
        return [w.name for w in (await db.execute(select(Widget))).scalars()]

    async with (
        LifespanManager(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as http,
    ):
        a = await http.get("/test/widgets", headers={"x-test-company": str(COMPANY_A)})
        b = await http.get("/test/widgets", headers={"x-test-company": str(COMPANY_B)})
        nobody = await http.get("/test/global")
    assert a.json() == ["a-1", "a-2", "a-3"]
    assert b.json() == ["b-1", "b-2"]
    assert nobody.json() == []  # tenant tables are invisible without a company
