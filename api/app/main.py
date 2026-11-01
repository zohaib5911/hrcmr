"""FastAPI application factory.

Run locally:      uv run uvicorn app.main:create_app --factory --reload --port 8000
Run in container: gunicorn -c gunicorn.conf.py "app.main:create_app()"
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from functools import partial
from typing import TYPE_CHECKING

from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware
from app.core.redis import create_redis, ping_redis
from app.db.engine import create_engine, ping_database
from app.modules.health.router import router as health_router

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

API_PREFIX = "/api/v1"
logger = get_logger("app.main")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings)
        redis = create_redis(settings)
        app.state.probes = {
            "database": partial(ping_database, engine),
            "redis": partial(ping_redis, redis),
        }
        logger.info("startup", app_env=settings.app_env.value)
        try:
            yield
        finally:
            await redis.aclose()
            await engine.dispose()
            logger.info("shutdown")

    app = FastAPI(
        title="Platform API",
        version="0.1.0",
        lifespan=lifespan,
        # Docs are local-only; deployed environments get them via the super-admin API later.
        docs_url=f"{API_PREFIX}/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json" if settings.docs_enabled else None,
    )
    app.state.settings = settings
    app.state.probes = {}

    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    app.include_router(health_router, prefix=API_PREFIX)
    return app
