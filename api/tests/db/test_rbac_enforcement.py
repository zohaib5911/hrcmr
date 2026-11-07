"""T2.5: `require()` in a running app (every role against a sample of every kind of permission),
the reports-chain query, the role rules, and the guard that no endpoint skips authorisation."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.dependencies.utils import solve_dependencies
from redis.asyncio import Redis
from sqlalchemy import event, text
from sqlalchemy.pool import NullPool

from app.core.crypto import KeyRing, set_keyring
from app.core.errors import AppError, ForbiddenError
from app.core.rbac_matrix import ROLES, Scope, has_permission, scope_for
from app.db.ids import uuid7
from app.db.session import GlobalSession, TenantSession
from app.main import create_app
from app.modules.auth.sessions import SessionStore
from app.modules.rbac.deps import Access, require
from app.modules.rbac.reports import ReportsGraph
from app.modules.rbac.rules import (
    LastCompanyAdminError,
    check_can_change_role,
    check_can_invite,
    ensure_company_keeps_an_admin,
    forbid_self_approval,
)
from tests.db.api_support import two_companies
from tests.db.support import DatabaseUnderTest, engine_for
from tests.route_support import permissions, registered_routes
from tests.support import TEST_REDIS_URL, build_settings

CSRF = "a-test-csrf-token"
# One permission of every kind: whole-company, reports-only, own-only, and the ones that only the
# top role has. (The full 120 x 6 table is checked as data in tests/test_rbac_matrix.py.)
SAMPLE = [
    "employee.profile.read",
    "employee.profile.write",
    "employee.profile.delete",
    "employee.sensitive_data.read",
    "employee.compensation.read",
    "attendance.record.read",
    "attendance.record.write",
    "attendance.timesheet.approve_reports",
    "leave.request.approve",
    "leave.request.create",
    "leave.type.write",
    "recruitment.requisition.approve",
    "recruitment.candidate.read",
    "rbac.role.assign",
    "rbac.user.invite",
    "rbac.user.read",
    "company.profile.write",
    "company.overview.read",
    "document.report.generate",
    "policy.acceptance.write",
    "compliance.audit.export",
    "soc.check.run",
    "ai.letter.draft",
    "billing.manage",
    "company.delete",
]


def probe_router() -> APIRouter:
    router = APIRouter(prefix="/probe")

    def add(permission: str) -> None:
        dependency = Depends(require(permission))

        @router.get(f"/{permission}")
        async def probe(access: Access = dependency) -> dict[str, str]:
            return {"scope": access.scope.value, "role": access.role}

    for permission in SAMPLE:
        add(permission)
    return router


class Setup:
    def __init__(self, client: httpx.AsyncClient, db: DatabaseUnderTest, sessions: SessionStore):
        self.client, self.db, self.sessions = client, db, sessions
        self.company = uuid7()

    async def owner(self, statement: str, **params: Any) -> list[Any]:
        engine = engine_for(self.db.owner_url, poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                result = await connection.execute(text(statement), params)
                return list(result.all()) if result.returns_rows else []
        finally:
            await engine.dispose()

    async def person(
        self,
        role: str,
        *,
        verified: bool = True,
        accept_terms: bool = True,
        company: uuid.UUID | None = None,
    ) -> httpx.AsyncClient:
        """A browser signed in as a new person with this role in the company."""
        user = uuid7()
        await self.owner(
            "insert into users (id, email, first_name, last_name, password_hash, email_verified_at) "
            "values (:u, :e, 'F', 'L', 'x', case when :v then now() end)",
            u=user,
            e=f"{role}-{user}@example.com",
            v=verified,
        )
        await self.owner(
            "insert into memberships (user_id, company_id, role) values (:u, :c, :r)",
            u=user,
            c=company or self.company,
            r=role,
        )
        if accept_terms:
            await self.owner(
                "insert into terms_acceptances (user_id, version) "
                "select :u, version from terms_versions",
                u=user,
            )
        engine = engine_for(self.db.app_url, poolclass=NullPool)
        try:
            async with GlobalSession(engine) as session:
                token, _ = await self.sessions.create(
                    session,
                    user_id=user,
                    company_id=company or self.company,
                    ip=None,
                    user_agent=None,
                    mfa_passed=True,
                )
                await session.commit()
        finally:
            await engine.dispose()
        browser = httpx.AsyncClient(transport=self.client._transport, base_url="http://test")
        browser.cookies.set("brand_session", token)
        return browser


@pytest.fixture
async def setup(database: DatabaseUnderTest) -> AsyncIterator[Setup]:
    set_keyring(KeyRing(keys={"k1": os.urandom(32)}, active_kid="k1", blind_key=os.urandom(32)))
    redis = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    await redis.flushdb()
    settings = build_settings(database_url=database.app_url, redis_url=TEST_REDIS_URL)
    app = create_app(settings)
    app.include_router(probe_router(), prefix="/api/v1")
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            ctx = Setup(client, database, SessionStore(redis))
            await ctx.owner("truncate users, companies cascade")
            await ctx.owner(
                "insert into companies (id, name, slug) values (:i, 'Co', 'co')", i=ctx.company
            )
            yield ctx
    await redis.flushdb()
    await redis.aclose()
    set_keyring(None)


# --- require() ------------------------------------------------------------------------------------


@pytest.mark.parametrize("role", ROLES)
async def test_each_role_is_admitted_exactly_where_the_matrix_says(setup: Setup, role: str) -> None:
    browser = await setup.person(role)
    async with browser:
        for permission in SAMPLE:
            response = await browser.get(f"/api/v1/probe/{permission}")
            expected = scope_for(role, permission)
            if expected is None:
                assert response.status_code == 403, (role, permission)
                assert response.json()["error"]["code"] == "FORBIDDEN"
            else:
                assert response.status_code == 200, (role, permission)
                assert response.json() == {"scope": expected.value, "role": role}
            assert (expected is not None) == has_permission(role, permission) or expected in {
                Scope.OWN,
                Scope.REPORTS,
            }


async def test_nobody_gets_in_without_a_session(setup: Setup) -> None:
    response = await setup.client.get("/api/v1/probe/company.overview.read")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_standing_checks_come_before_the_permission(setup: Setup) -> None:
    async with await setup.person("company_admin", verified=False) as unverified:
        refused = await unverified.get("/api/v1/probe/company.overview.read")
        assert refused.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"
    async with await setup.person("company_admin", accept_terms=False) as no_terms:
        refused = await no_terms.get("/api/v1/probe/company.overview.read")
        assert refused.json()["error"]["code"] == "TERMS_ACCEPTANCE_REQUIRED"

    await setup.owner("update companies set mfa_policy = 'admins'")
    async with await setup.person("company_admin") as admin:
        refused = await admin.get("/api/v1/probe/company.overview.read")
        assert refused.status_code == 403
        assert refused.json()["error"]["code"] == "MFA_ENROLMENT_REQUIRED"  # policy asks admins
    async with await setup.person("employee") as employee:  # but not everyone
        assert (await employee.get("/api/v1/probe/company.overview.read")).status_code == 200

    await setup.owner("update companies set mfa_policy = 'optional'")
    await setup.owner("update memberships set status = 'suspended' where role = 'employee'")
    async with await setup.person("employee") as fresh:
        await setup.owner("update memberships set status = 'suspended'")
        suspended = await fresh.get("/api/v1/probe/company.overview.read")
        assert suspended.json()["error"]["code"] == "ACCOUNT_SUSPENDED"


async def test_a_session_with_no_company_is_asked_to_choose_one(setup: Setup) -> None:
    async with await setup.person("company_admin") as browser:
        token = browser.cookies.get("brand_session")
        assert token
        data = await setup.sessions.get(token)
        assert data is not None
        engine = engine_for(setup.db.app_url, poolclass=NullPool)
        try:
            async with GlobalSession(engine) as db:
                other, _ = await setup.sessions.rotate(
                    db, token, data, change_company=True, company_id=None
                )
                await db.commit()
        finally:
            await engine.dispose()
        browser.cookies.set("brand_session", other)
        response = await browser.get("/api/v1/probe/company.overview.read")
        assert response.json()["error"]["code"] == "NO_COMPANY"


async def test_a_company_the_person_does_not_belong_to_is_refused(setup: Setup) -> None:
    other = uuid7()
    await setup.owner(
        "insert into companies (id, name, slug) values (:i, 'Other', 'other')", i=other
    )
    async with await setup.person("company_admin") as browser:
        token = browser.cookies.get("brand_session")
        assert token
        data = await setup.sessions.get(token)
        assert data is not None
        engine = engine_for(setup.db.app_url, poolclass=NullPool)
        try:
            async with GlobalSession(engine) as db:
                forged, _ = await setup.sessions.rotate(
                    db, token, data, change_company=True, company_id=other
                )
                await db.commit()
        finally:
            await engine.dispose()
        browser.cookies.set("brand_session", forged)
        response = await browser.get("/api/v1/probe/company.overview.read")
        assert response.status_code == 403


def test_asking_for_a_permission_that_does_not_exist_fails_at_start_up() -> None:
    with pytest.raises(ValueError, match="unknown permission"):
        require("employee.profile.redd")


def test_no_real_endpoint_skips_authorisation() -> None:
    """Every route is either behind `require()` or on this short, reviewed list. Adding an endpoint
    without a permission fails here, so the RBAC matrix cannot quietly miss one."""
    allowed_prefixes = (
        "/api/v1/auth/",  # sign-in and account flows: each does its own checks (see test_auth_*)
        "/api/v1/health",
        "/api/v1/ready",
        "/api/v1/public/careers/",  # no-login careers pages and apply: Turnstile, rate limit, listed fields
        "/api/v1/public/postings/",  # (see test_careers)
        "/api/v1/public/certificates/",  # no-login certificate check: rate limited, four fields only (see test_certificates)
    )

    app: FastAPI = create_app(build_settings())
    routes = registered_routes(app)
    actual = {
        (path.removeprefix("/api/v1"), method.lower())
        for path, methods, _ in routes
        for method in methods
    }
    documented = {
        (path, method)
        for path, item in app.openapi()["paths"].items()
        for method in item
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert actual == documented  # never silently test zero deferred routes
    assert len(routes) > 100
    unprotected = [
        f"{sorted(methods)} {path}"
        for path, methods, dep in routes
        if not path.startswith(allowed_prefixes) and not permissions(dep)
    ]
    assert unprotected == []


@pytest.mark.parametrize("role", ROLES)
async def test_every_real_routes_permission_dependencies_match_the_matrix(
    setup: Setup, role: str
) -> None:
    """Resolve each real route's entire guard graph, stopping before validation/business effects.

    Missing bodies/IDs can produce validation errors after guards resolve; admitted Access objects
    must still carry exactly the matrix scope. Resource reach and handler rules have separate tests.
    """
    app = setup.client._transport.app  # type: ignore[attr-defined]
    browser = await setup.person(role)
    checked = 0
    async with browser:
        for path, methods, dependant in registered_routes(app):
            if path.startswith("/api/v1/probe/"):
                continue
            required = permissions(dependant)
            if not required:
                assert path.startswith(
                    ("/api/v1/auth/", "/api/v1/health", "/api/v1/ready", "/api/v1/public/")
                ), path
                continue
            expected = {permission: scope_for(role, permission) for permission in required}
            admitted = all(scope is not None for scope in expected.values())
            for method in methods:
                async with AsyncExitStack() as stack:
                    request = Request(
                        {
                            "type": "http",
                            "app": app,
                            "method": method,
                            "path": path,
                            "query_string": b"",
                            "path_params": {},
                            "headers": [
                                (
                                    b"cookie",
                                    f"brand_session={browser.cookies.get('brand_session')}".encode(),
                                )
                            ],
                            "client": ("127.0.0.1", 1234),
                            "scheme": "http",
                            "server": ("test", 80),
                            "fastapi_inner_astack": stack,
                            "fastapi_function_astack": stack,
                        }
                    )
                    if admitted:
                        solved = await solve_dependencies(
                            request=request,
                            dependant=dependant,
                            async_exit_stack=stack,
                            embed_body_fields=False,
                            dependency_overrides_provider=app,
                        )
                        accesses = [
                            value
                            for value in solved.dependency_cache.values()
                            if isinstance(value, Access)
                        ]
                        assert {value.permission: value.scope for value in accesses} == expected, (
                            method,
                            path,
                            role,
                        )
                    else:
                        with pytest.raises(AppError) as raised:
                            await solve_dependencies(
                                request=request,
                                dependant=dependant,
                                async_exit_stack=stack,
                                embed_body_fields=False,
                                dependency_overrides_provider=app,
                            )
                        assert raised.value.code == "FORBIDDEN", (
                            method,
                            path,
                            role,
                            raised.value.code,
                        )
                    checked += 1
    assert checked > 150


# --- the reports chain ------------------------------------------------------------------------------


async def test_reports_are_found_at_any_depth_per_chain_and_never_across_companies(
    database: DatabaseUnderTest,
) -> None:
    company_a, company_b = await two_companies(database)
    ceo, vp, lead, dev, other = (uuid7() for _ in range(5))
    loop_x, loop_y, outsider = uuid7(), uuid7(), uuid7()
    future, past = uuid7(), uuid7()
    rows = [
        (ceo, company_a, None, None),
        (vp, company_a, ceo, lead),  # reports to the CEO; leave goes to the lead
        (lead, company_a, vp, None),
        (dev, company_a, lead, vp),
        (other, company_a, None, None),
        (loop_x, company_a, loop_y, None),  # a loop in the data must not hang the query
        (loop_y, company_a, loop_x, None),
        (outsider, company_b, ceo, None),  # another company, pointing at our CEO
    ]
    owner = engine_for(database.owner_url, poolclass=NullPool)
    async with owner.begin() as c:
        # Use the migrated schema: this database is shared with later tests.
        for ident, company in [(r[0], r[1]) for r in rows] + [
            (future, company_a),
            (past, company_a),
        ]:
            await c.execute(
                text(
                    "insert into employees (id, company_id, employee_number, first_name, last_name, email, hire_date) "
                    "values (:i, :c, :n, 'Test', 'Person', 'test@example.com', '2000-01-01')"
                ),
                {"i": ident, "c": company, "n": str(ident)},
            )
        for row in rows:
            await c.execute(
                text(
                    "insert into employee_assignments (employee_id, company_id, reporting_authority_employee_id, leave_sanctioning_employee_id, employment_type, effective_from) values (:i, :c, :r, :l, 'full_time', '2000-01-01')"
                ),
                {"i": row[0], "c": row[1], "r": row[2], "l": row[3]},
            )
        # A planned future report and an ended report must not grant access today.
        await c.execute(
            text(
                "insert into employee_assignments (employee_id, company_id, "
                "reporting_authority_employee_id, effective_from, ended_at, employment_type) values "
                "(:future, :company, :ceo, '2099-01-01', null, 'full_time'), "
                "(:past, :company, :ceo, '2000-01-01', '2001-01-01', 'full_time')"
            ),
            {"future": future, "past": past, "company": company_a, "ceo": ceo},
        )
    await owner.dispose()

    app_engine = engine_for(database.app_url, poolclass=NullPool)
    queries: list[str] = []

    @event.listens_for(app_engine.sync_engine, "before_cursor_execute")
    def count(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        if "employee_assignments" in statement:
            queries.append(statement)

    try:
        async with TenantSession(app_engine, company_id=company_a) as db:
            graph = ReportsGraph(db, company_a)
            assert await graph.reports_of(ceo) == {vp, lead, dev}
            assert await graph.reports_of(vp) == {lead, dev}
            assert await graph.reports_of(dev) == frozenset()
            assert await graph.reports_of(other) == frozenset()
            assert await graph.reports_of(vp, "leave") == {dev}  # dev's leave goes to vp
            assert await graph.reports_of(lead, "leave") == {
                vp,
                dev,
            }  # vp's goes to lead, so dev too
            assert await graph.reports_of(loop_x) == {loop_y}  # not including themselves
            assert await graph.is_report(ceo, dev)
            assert not await graph.is_report(dev, ceo)
            assert outsider not in await graph.reports_of(ceo)  # company B's row is invisible
            before = len(queries)
            await graph.reports_of(ceo)
            await graph.reports_of(ceo)
            assert len(queries) == before  # remembered for the rest of the request
    finally:
        await app_engine.dispose()


# --- the rules about roles ------------------------------------------------------------------------------


def test_invitations_and_role_changes_follow_who_may_do_what() -> None:
    check_can_invite("company_admin", "company_admin")
    check_can_invite("hr_admin", "employee")
    with pytest.raises(ForbiddenError):
        check_can_invite("hr_admin", "company_admin")
    with pytest.raises(ForbiddenError):
        check_can_invite("employee", "employee")

    check_can_change_role("company_admin", current_role="employee", new_role="hr_admin")
    check_can_change_role("company_admin", current_role="company_admin", new_role="employee")
    with pytest.raises(ForbiddenError):  # HR Admins cannot assign roles at all
        check_can_change_role("hr_admin", current_role="employee", new_role="recruiter")


def test_no_one_approves_their_own_request() -> None:
    me, someone = uuid7(), uuid7()
    forbid_self_approval(me, someone)
    forbid_self_approval(None, someone)
    with pytest.raises(AppError) as raised:
        forbid_self_approval(me, me)
    assert raised.value.code == "SELF_APPROVAL"


async def test_a_company_always_keeps_one_active_company_admin(database: DatabaseUnderTest) -> None:
    company = uuid7()
    owner = engine_for(database.owner_url, poolclass=NullPool)
    admin_1, admin_2, member = uuid7(), uuid7(), uuid7()
    async with owner.begin() as c:
        await c.execute(text("truncate users, companies cascade"))
        await c.execute(
            text("insert into companies (id, name, slug) values (:i, 'Co', 'co')"), {"i": company}
        )
        for membership, role in ((admin_1, "company_admin"), (member, "employee")):
            user = uuid7()
            await c.execute(
                text(
                    "insert into users (id, email, first_name, last_name) values (:u, :e, 'F', 'L')"
                ),
                {"u": user, "e": f"{membership}@example.com"},
            )
            await c.execute(
                text(
                    "insert into memberships (id, user_id, company_id, role) values (:m, :u, :c, :r)"
                ),
                {"m": membership, "u": user, "c": company, "r": role},
            )
    await owner.dispose()

    engine = engine_for(database.app_url, poolclass=NullPool)
    try:
        async with TenantSession(engine, company_id=company) as db:
            for attempt in (
                {"new_role": "employee"},
                {"new_status": "suspended"},
                {"removing": True},
            ):
                with pytest.raises(LastCompanyAdminError):
                    await ensure_company_keeps_an_admin(db, company, admin_1, **attempt)
            # Changes that leave an admin in place, or that are not about an admin, are fine.
            await ensure_company_keeps_an_admin(db, company, admin_1, new_role="company_admin")
            await ensure_company_keeps_an_admin(db, company, member, new_status="suspended")
            await ensure_company_keeps_an_admin(db, company, member, removing=True)
    finally:
        await engine.dispose()

    owner = engine_for(database.owner_url, poolclass=NullPool)
    async with owner.begin() as c:
        user = uuid7()
        await c.execute(
            text(
                "insert into users (id, email, first_name, last_name) values (:u, 'two@example.com', 'F', 'L')"
            ),
            {"u": user},
        )
        await c.execute(
            text(
                "insert into memberships (id, user_id, company_id, role) values (:m, :u, :c, 'company_admin')"
            ),
            {"m": admin_2, "u": user, "c": company},
        )
    await owner.dispose()
    engine = engine_for(database.app_url, poolclass=NullPool)
    try:
        async with TenantSession(engine, company_id=company) as db:
            await ensure_company_keeps_an_admin(
                db, company, admin_1, new_role="employee"
            )  # now fine
    finally:
        await engine.dispose()
