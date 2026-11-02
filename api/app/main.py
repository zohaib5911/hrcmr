"""FastAPI application factory.

Run locally:      uv run uvicorn app.main:create_app --factory --reload --port 8000
Run in container: gunicorn -c gunicorn.conf.py "app.main:create_app()"
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from functools import partial
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.body_limit import LOGO_LIMIT, PROOF_LIMIT, UPLOAD_LIMIT, BodyLimitMiddleware
from app.core.config import Settings, get_settings
from app.core.csrf import CsrfMiddleware
from app.core.errors import ErrorEnvelope, register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware
from app.core.redis import create_redis, ping_redis
from app.db.engine import create_engine, ping_database
from app.integrations.clamav import ClamAV
from app.integrations.companies_house import CompaniesHouse
from app.integrations.email import LoggingMailer, Mailer, transport_from_settings
from app.integrations.postcodes import Postcodes
from app.integrations.storage import Storage
from app.integrations.turnstile import Turnstile
from app.jobs.queue import open_queue
from app.modules.audit.router import router as audit_router
from app.modules.auth.container import build_container
from app.modules.auth.router import router as auth_router
from app.modules.companies.compliance_documents import router as compliance_router
from app.modules.companies.key_personnel_router import router as key_personnel_router
from app.modules.companies.router import router as company_router
from app.modules.companies.structure_router import router as structure_router
from app.modules.companies.trading_hours import router as trading_hours_router
from app.modules.email.outbox import OutboxMailer
from app.modules.files.router import router as files_router
from app.modules.files.service import FileService
from app.modules.health.router import router as health_router
from app.modules.holidays.router import router as holidays_router
from app.modules.pay.router import router as pay_router

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi.routing import APIRoute

API_PREFIX = "/api/v1"
# Every operation can fail with our error envelope. Declaring the 4XX and 5XX ranges documents it
# for the generated TypeScript client, and stops FastAPI from advertising its own, different
# `HTTPValidationError` shape for 422, which this API never returns.
ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    "4XX": {
        "model": ErrorEnvelope,
        "description": "The request could not be completed. `error.code` says why.",
    },
    "5XX": {
        "model": ErrorEnvelope,
        "description": "Something failed on our side. Quote `error.request_id` to support.",
    },
}
logger = get_logger("app.main")


def operation_id(route: APIRoute) -> str:
    """Readable, stable operation ids (`health_ready`) for the generated TypeScript client."""
    return f"{route.tags[0]}_{route.name}" if route.tags else route.name


def _install_openapi(app: FastAPI) -> None:
    """Describe the API the way a client calls it: paths relative to the `/api/v1` server.

    The web app's base URL (NEXT_PUBLIC_API_URL) already ends in `/api/v1`, so documenting
    `/api/v1/health` would make the generated client request `/api/v1/api/v1/health`.
    """
    build = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            schema = build()
            schema["paths"] = {
                path.removeprefix(API_PREFIX) or "/": item for path, item in schema["paths"].items()
            }
            schema["servers"] = [{"url": API_PREFIX}]
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]


def create_app(settings: Settings | None = None, *, mailer: Mailer | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings)
        redis = create_redis(settings)
        app.state.engine = engine
        queue = None
        sender = mailer
        if sender is None and transport_from_settings(settings) is not None:
            # A mail service is set up: messages are saved, then the worker sends them.
            queue = await open_queue(settings)
            sender = OutboxMailer(engine, queue)
        app.state.auth = build_container(
            settings, redis, sender or LoggingMailer(), Turnstile(settings.turnstile_secret_key)
        )
        app.state.companies_house = CompaniesHouse.from_settings(settings)
        app.state.postcodes = Postcodes()
        app.state.files = FileService(
            Storage.from_settings(settings), ClamAV.from_settings(settings)
        )
        app.state.probes = {
            "database": partial(ping_database, engine),
            "redis": partial(ping_redis, redis),
        }
        logger.info("startup", app_env=settings.app_env.value)
        try:
            yield
        finally:
            if queue is not None:
                await queue.close()
            await redis.aclose()
            await engine.dispose()
            logger.info("shutdown")

    app = FastAPI(
        title="Platform API",
        version="0.1.0",
        lifespan=lifespan,
        responses=ERROR_RESPONSES,
        generate_unique_id_function=operation_id,
        # Docs are local-only; deployed environments get them via the super-admin API later.
        docs_url=f"{API_PREFIX}/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json" if settings.docs_enabled else None,
    )
    app.state.settings = settings
    app.state.probes = {}

    # Added first so it sits inside the request-id middleware and its refusals carry the request id.
    app.add_middleware(
        BodyLimitMiddleware,
        limits={
            f"{API_PREFIX}/files": UPLOAD_LIMIT,
            f"{API_PREFIX}/company/logo": LOGO_LIMIT,
            f"{API_PREFIX}/key-personnel": PROOF_LIMIT,
            f"{API_PREFIX}/compliance-documents": UPLOAD_LIMIT,
        },
    )
    app.add_middleware(
        CsrfMiddleware,
        secure=settings.app_env.is_deployed,
        cookie_domain=f".{settings.domain}" if settings.app_env.is_deployed else None,
    )
    app.add_middleware(RequestContextMiddleware)
    # Outermost, so even a refusal (CSRF, rate limit) carries the headers the browser needs to show
    # it. Only our own two origins, with credentials: never a wildcard (plan 4.2).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin, settings.admin_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
        max_age=600,
    )
    register_exception_handlers(app)
    app.include_router(health_router, prefix=API_PREFIX)
    app.include_router(auth_router, prefix=API_PREFIX)
    app.include_router(audit_router, prefix=API_PREFIX)
    app.include_router(files_router, prefix=API_PREFIX)
    app.include_router(company_router, prefix=API_PREFIX)
    app.include_router(key_personnel_router, prefix=API_PREFIX)
    app.include_router(compliance_router, prefix=API_PREFIX)
    app.include_router(holidays_router, prefix=API_PREFIX)
    app.include_router(trading_hours_router, prefix=API_PREFIX)
    app.include_router(pay_router, prefix=API_PREFIX)
    app.include_router(structure_router, prefix=API_PREFIX)
    _install_openapi(app)
    return app
