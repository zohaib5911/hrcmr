"""FastAPI application factory.

Run locally:      uv run uvicorn app.main:create_app --factory --reload --port 8000
Run in container: gunicorn -c gunicorn.conf.py "app.main:create_app()"
"""

from __future__ import annotations

import asyncio
import re
from contextlib import asynccontextmanager
from functools import partial
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai.letters import router as letters_router
from app.core.body_limit import (
    LOGO_LIMIT,
    PROOF_LIMIT,
    SMALL_FILE_LIMIT,
    UPLOAD_LIMIT,
    BodyLimitMiddleware,
)
from app.core.config import Settings, get_settings
from app.core.csrf import CsrfMiddleware
from app.core.errors import ErrorEnvelope, register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.core.redis import create_redis, ping_redis
from app.db.engine import create_engine, ping_database
from app.integrations.anthropic import Anthropic
from app.integrations.clamav import ClamAV
from app.integrations.cloudflare_ips import keep_cloudflare_ranges_current
from app.integrations.companies_house import CompaniesHouse
from app.integrations.email import LoggingMailer, Mailer, transport_from_settings
from app.integrations.postcodes import Postcodes
from app.integrations.storage import Storage
from app.integrations.stripe import Stripe
from app.integrations.turnstile import Turnstile
from app.jobs.queue import open_queue
from app.modules.access.router import router as access_router
from app.modules.announcements.router import router as announcements_router
from app.modules.attendance.batch_router import router as attendance_batch_router
from app.modules.attendance.clock_router import router as attendance_clock_router
from app.modules.attendance.import_router import router as attendance_import_router
from app.modules.attendance.router import router as attendance_router
from app.modules.audit.router import router as audit_router
from app.modules.auth.container import build_container
from app.modules.auth.router import router as auth_router
from app.modules.billing.router import router as billing_router
from app.modules.billing.router import webhook_router as stripe_webhook_router
from app.modules.companies.compliance_documents import router as compliance_router
from app.modules.companies.key_personnel_router import router as key_personnel_router
from app.modules.companies.router import router as company_router
from app.modules.companies.structure_router import router as structure_router
from app.modules.companies.trading_hours import router as trading_hours_router
from app.modules.compliance.activity_router import router as compliance_activity_router
from app.modules.compliance.dossier_router import router as dossier_router
from app.modules.compliance.hub_router import router as compliance_hub_router
from app.modules.compliance.reminder_router import router as reminders_router
from app.modules.compliance.router import router as compliance_changes_router
from app.modules.compliance.sponsor_pdf import router as sponsor_pdf_router
from app.modules.contact.public import router as contact_public_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.deletion.router import router as deletion_router
from app.modules.documents.router import router as documents_router
from app.modules.email.outbox import OutboxMailer
from app.modules.employees.activity_router import router as employee_activity_router
from app.modules.employees.compensation_router import router as compensation_router
from app.modules.employees.document_router import router as employee_documents_router
from app.modules.employees.employment_router import router as employment_router
from app.modules.employees.personal_router import router as personal_router
from app.modules.employees.photo_router import router as employee_photo_router
from app.modules.employees.record_pdf import router as employee_pdf_router
from app.modules.employees.router import router as employees_router
from app.modules.exports.router import router as exports_router
from app.modules.files.router import router as files_router
from app.modules.files.service import FileService
from app.modules.health.router import router as health_router
from app.modules.holidays.router import router as holidays_router
from app.modules.learning.admin_router import router as learning_admin_router
from app.modules.learning.certificates import router as certificates_router
from app.modules.learning.router import router as learning_router
from app.modules.leave.request_router import router as leave_requests_router
from app.modules.leave.router import router as leave_router
from app.modules.leave.workspace_router import router as leave_workspace_router
from app.modules.leave.year_end_router import router as leave_year_end_router
from app.modules.notifications.router import router as notifications_router
from app.modules.organogram.router import router as organogram_router
from app.modules.pay.router import router as pay_router
from app.modules.platform_admin.router import router as platform_admin_router
from app.modules.policies.own_router import router as own_policies_router
from app.modules.policies.router import router as policies_router
from app.modules.rbac.platform_session import router as platform_session_router
from app.modules.recruitment.public import router as careers_router
from app.modules.recruitment.router import router as recruitment_router
from app.modules.register.public import router as register_public_router
from app.modules.reports.router import router as reports_router
from app.modules.rota.action_router import router as rota_action_router
from app.modules.rota.publish_router import router as rota_publish_router
from app.modules.rota.router import router as rota_router
from app.modules.rota.week_router import router as rota_week_router
from app.modules.rtw.router import router as rtw_router
from app.modules.search.router import router as search_router
from app.modules.soc.checks_router import router as soc_checks_router
from app.modules.soc.cv_router import router as soc_cv_router
from app.modules.soc.public_router import router as soc_public_router
from app.modules.soc.router import router as soc_router
from app.modules.soc_rules.admin_router import router as rules_admin_router
from app.modules.sponsor_documents.router import router as sponsor_documents_router
from app.modules.support.router import router as support_router
from app.modules.work_log.router import router as work_log_router

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
    tag = str(route.tags[0]).replace("-", "_") if route.tags else None
    return f"{tag}_{route.name}" if tag else route.name


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
        app.state.anthropic = Anthropic.from_settings(settings)
        app.state.stripe = Stripe.from_settings(settings)
        app.state.postcodes = Postcodes()
        app.state.files = FileService(
            Storage.from_settings(settings), ClamAV.from_settings(settings)
        )
        app.state.probes = {
            "database": partial(ping_database, engine),
            "redis": partial(ping_redis, redis),
        }
        logger.info("startup", app_env=settings.app_env.value)
        refresher = asyncio.create_task(keep_cloudflare_ranges_current(redis))
        try:
            yield
        finally:
            refresher.cancel()
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
            # The careers apply form: a CV of up to 10 MB and its fields.
            f"{API_PREFIX}/public/postings": PROOF_LIMIT,
            # The SOC CV match: a CV of up to 10 MB and the job description.
            f"{API_PREFIX}/soc/resume-match": PROOF_LIMIT,
            f"{API_PREFIX}/attendance/import/preview": SMALL_FILE_LIMIT,
            # Upload routes whose prefix also serves JSON: the whole path must match.
            re.compile(rf"{API_PREFIX}/documents"): UPLOAD_LIMIT,
            re.compile(rf"{API_PREFIX}/policies/[^/]+/file"): UPLOAD_LIMIT,
            re.compile(rf"{API_PREFIX}/employees/[^/]+/documents"): UPLOAD_LIMIT,
            re.compile(rf"{API_PREFIX}/employees/[^/]+/opt-out-48h/agreement"): UPLOAD_LIMIT,
            re.compile(rf"{API_PREFIX}/employees/[^/]+/photo"): SMALL_FILE_LIMIT,
        },
    )
    app.add_middleware(
        CsrfMiddleware,
        secure=settings.app_env.is_deployed,
        cookie_domain=f".{settings.domain}" if settings.app_env.is_deployed else None,
    )
    app.add_middleware(SecurityHeadersMiddleware)
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
    app.include_router(announcements_router, prefix=API_PREFIX)
    app.include_router(key_personnel_router, prefix=API_PREFIX)
    app.include_router(compliance_router, prefix=API_PREFIX)
    app.include_router(holidays_router, prefix=API_PREFIX)
    app.include_router(leave_router, prefix=API_PREFIX)
    app.include_router(leave_requests_router, prefix=API_PREFIX)
    app.include_router(leave_workspace_router, prefix=API_PREFIX)
    app.include_router(leave_year_end_router, prefix=API_PREFIX)
    app.include_router(attendance_router, prefix=API_PREFIX)
    app.include_router(attendance_import_router, prefix=API_PREFIX)
    app.include_router(attendance_batch_router, prefix=API_PREFIX)
    app.include_router(attendance_clock_router, prefix=API_PREFIX)
    app.include_router(rota_router, prefix=API_PREFIX)
    app.include_router(rota_week_router, prefix=API_PREFIX)
    app.include_router(rota_action_router, prefix=API_PREFIX)
    app.include_router(rota_publish_router, prefix=API_PREFIX)
    app.include_router(work_log_router, prefix=API_PREFIX)
    app.include_router(trading_hours_router, prefix=API_PREFIX)
    app.include_router(pay_router, prefix=API_PREFIX)
    app.include_router(access_router, prefix=API_PREFIX)
    app.include_router(employees_router, prefix=API_PREFIX)
    app.include_router(personal_router, prefix=API_PREFIX)
    app.include_router(employment_router, prefix=API_PREFIX)
    app.include_router(own_policies_router, prefix=API_PREFIX)
    app.include_router(policies_router, prefix=API_PREFIX)
    app.include_router(reports_router, prefix=API_PREFIX)
    app.include_router(exports_router, prefix=API_PREFIX)
    app.include_router(deletion_router, prefix=API_PREFIX)
    app.include_router(documents_router, prefix=API_PREFIX)
    app.include_router(letters_router, prefix=API_PREFIX)
    app.include_router(recruitment_router, prefix=API_PREFIX)
    app.include_router(organogram_router, prefix=API_PREFIX)
    app.include_router(learning_router, prefix=API_PREFIX)
    app.include_router(learning_admin_router, prefix=API_PREFIX)
    app.include_router(platform_session_router, prefix=API_PREFIX)
    app.include_router(certificates_router, prefix=API_PREFIX)
    app.include_router(dashboard_router, prefix=API_PREFIX)
    app.include_router(search_router, prefix=API_PREFIX)
    app.include_router(soc_router, prefix=API_PREFIX)
    app.include_router(soc_cv_router, prefix=API_PREFIX)
    app.include_router(soc_checks_router, prefix=API_PREFIX)
    app.include_router(soc_public_router, prefix=API_PREFIX)
    app.include_router(rules_admin_router, prefix=API_PREFIX)
    app.include_router(platform_admin_router, prefix=API_PREFIX)
    app.include_router(support_router, prefix=API_PREFIX)
    app.include_router(careers_router, prefix=API_PREFIX)
    app.include_router(contact_public_router, prefix=API_PREFIX)
    app.include_router(register_public_router, prefix=API_PREFIX)
    app.include_router(employee_documents_router, prefix=API_PREFIX)
    app.include_router(employee_pdf_router, prefix=API_PREFIX)
    app.include_router(employee_activity_router, prefix=API_PREFIX)
    app.include_router(rtw_router, prefix=API_PREFIX)
    app.include_router(compliance_changes_router, prefix=API_PREFIX)
    app.include_router(compliance_hub_router, prefix=API_PREFIX)
    app.include_router(dossier_router, prefix=API_PREFIX)
    app.include_router(sponsor_pdf_router, prefix=API_PREFIX)
    app.include_router(notifications_router, prefix=API_PREFIX)
    app.include_router(compliance_activity_router, prefix=API_PREFIX)
    app.include_router(reminders_router, prefix=API_PREFIX)
    app.include_router(sponsor_documents_router, prefix=API_PREFIX)
    app.include_router(employee_photo_router, prefix=API_PREFIX)
    app.include_router(compensation_router, prefix=API_PREFIX)
    app.include_router(structure_router, prefix=API_PREFIX)
    app.include_router(billing_router, prefix=API_PREFIX)
    app.include_router(stripe_webhook_router, prefix=API_PREFIX)
    _install_openapi(app)
    return app
