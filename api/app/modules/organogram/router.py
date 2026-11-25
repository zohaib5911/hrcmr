"""The org chart and its hierarchy levels (plan 8.13, API item 16)."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select

from app.core.errors import ConflictError
from app.core.rbac_matrix import Scope, scope_for
from app.db.ids import uuid7
from app.modules.employees.record_pdf import render_pdf_async
from app.modules.organogram import service
from app.modules.organogram.models import OrganogramLevel
from app.modules.organogram.pdf import org_chart_html
from app.modules.organogram.schemas import LevelIn, LevelOut, LevelPatch, OrgChartOut
from app.modules.rbac.deps import Access, require

router = APIRouter(tags=["organogram"])
Reads = Annotated[Access, Depends(require("organogram.level.read"))]
Writes = Annotated[Access, Depends(require("organogram.level.write"))]


def _level_out(row: OrganogramLevel) -> LevelOut:
    return LevelOut(id=row.id, name=row.name, rank=row.rank)


def _snapshot(row: OrganogramLevel) -> dict[str, Any]:
    return {"name": row.name, "rank": row.rank}


@router.get("/organogram", response_model=OrgChartOut)
async def org_chart(access: Reads) -> OrgChartOut:
    # Visa/RTW chips only for people who may read RTW for the whole company (not "own" only).
    with_rtw = scope_for(access.role, "employee.rtw.read") is Scope.ALL
    tree = await service.org_chart(
        access.db, access.company_id, with_rtw=with_rtw, today=await access.reports.today()
    )
    return OrgChartOut(rtw_visible=with_rtw, unassigned=tree)


@router.get(
    "/organogram.pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "The org chart as a PDF"}},
)
async def org_chart_pdf(access: Reads) -> Response:
    with_rtw = scope_for(access.role, "employee.rtw.read") is Scope.ALL
    tree = await service.org_chart(
        access.db, access.company_id, with_rtw=with_rtw, today=await access.reports.today()
    )
    generated = datetime.now(UTC).strftime("%d %b %Y %H:%M UTC")
    html = org_chart_html(
        [person.model_dump(mode="json") for person in tree],
        generated=generated,
        rtw_visible=with_rtw,
    )
    pdf = await render_pdf_async(html)
    await access.audit("organogram.exported")
    await access.db.commit()
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="org-chart.pdf"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/organogram/levels", response_model=list[LevelOut])
async def list_levels(access: Reads) -> list[LevelOut]:
    rows = (
        (
            await access.db.execute(
                select(OrganogramLevel)
                .where(OrganogramLevel.company_id == access.company_id)
                .order_by(OrganogramLevel.rank, func.lower(OrganogramLevel.name))
            )
        )
        .scalars()
        .all()
    )
    return [_level_out(row) for row in rows]


@router.post("/organogram/levels", status_code=201, response_model=LevelOut)
async def create_level(body: LevelIn, access: Writes) -> LevelOut:
    if await service.name_taken(access.db, access.company_id, body.name):
        raise ConflictError("A level with this name already exists.", field="name")
    rank = (
        body.rank
        if body.rank is not None
        else await service.next_rank(access.db, access.company_id)
    )
    row = OrganogramLevel(id=uuid7(), company_id=access.company_id, name=body.name, rank=rank)
    access.db.add(row)
    await access.db.flush()
    await access.db.refresh(row)
    await access.audit(
        "organogram.level.created",
        entity_type="organogram_level",
        entity_id=row.id,
        after=_snapshot(row),
    )
    await access.db.commit()
    return _level_out(row)


@router.patch("/organogram/levels/{level_id}", response_model=LevelOut)
async def update_level(level_id: uuid.UUID, body: LevelPatch, access: Writes) -> LevelOut:
    row = await service.level_or_404(access.db, access.company_id, level_id, lock=True)
    before = _snapshot(row)
    if body.name is not None and body.name != row.name:
        if await service.name_taken(access.db, access.company_id, body.name, except_id=row.id):
            raise ConflictError("A level with this name already exists.", field="name")
        row.name = body.name
    if body.rank is not None:
        row.rank = body.rank
    await access.db.flush()
    await access.db.refresh(row)
    await access.audit(
        "organogram.level.updated",
        entity_type="organogram_level",
        entity_id=row.id,
        before=before,
        after=_snapshot(row),
    )
    await access.db.commit()
    return _level_out(row)


@router.delete("/organogram/levels/{level_id}", status_code=204)
async def delete_level(level_id: uuid.UUID, access: Writes) -> None:
    row = await service.level_or_404(access.db, access.company_id, level_id, lock=True)
    if await service.level_in_use(access.db, access.company_id, row.id):
        raise ConflictError(
            "A role uses this level, so it cannot be removed. Rename it or change those roles."
        )
    ident = row.id
    before = _snapshot(row)
    await access.db.delete(row)
    await access.db.flush()
    await access.audit(
        "organogram.level.deleted",
        entity_type="organogram_level",
        entity_id=ident,
        before=before,
    )
    await access.db.commit()
