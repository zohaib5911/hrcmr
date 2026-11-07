"""The dashboard and the set-up checklist (plan 8.2, API item 18)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.modules.dashboard import service
from app.modules.dashboard.schemas import ChecklistOut, DashboardOut
from app.modules.rbac.deps import Access, require

router = APIRouter(tags=["dashboard"])
# Every role holds company.overview.read, so every signed-in person can open the dashboard; each
# card inside it checks its own permission. Setting up the company is for its administrators.
Home = Annotated[Access, Depends(require("company.overview.read"))]
Setup = Annotated[Access, Depends(require("company.profile.write"))]


@router.get("/dashboard", response_model=DashboardOut, response_model_exclude_none=True)
async def dashboard(access: Home) -> DashboardOut:
    return await service.dashboard(access)


@router.get("/onboarding/checklist", response_model=ChecklistOut)
async def checklist(access: Setup) -> ChecklistOut:
    return await service.checklist(access)


@router.post("/onboarding/checklist/dismiss", status_code=204, response_class=Response)
async def dismiss(access: Setup) -> Response:
    await service.dismiss(access)
    return Response(status_code=204)
