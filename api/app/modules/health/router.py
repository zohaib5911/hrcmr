from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.modules.health.schemas import HealthResponse, ReadyResponse
from app.modules.health.service import run_probes

router = APIRouter(tags=["health"])

_NO_STORE = "no-store"


@router.get("/health", summary="Liveness check")
async def health(response: Response) -> HealthResponse:
    response.headers["Cache-Control"] = _NO_STORE
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    summary="Readiness check (database and Redis)",
    responses={503: {"model": ReadyResponse, "description": "A dependency is not answering."}},
)
async def ready(request: Request, response: Response) -> ReadyResponse:
    response.headers["Cache-Control"] = _NO_STORE
    checks = await run_probes(request.app.state.probes)
    if all(result == "ok" for result in checks.values()):
        return ReadyResponse(status="ready", checks=checks)
    response.status_code = 503
    return ReadyResponse(status="not_ready", checks=checks)
