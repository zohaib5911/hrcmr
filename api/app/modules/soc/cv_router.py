"""``POST /soc/resume-match``: a CV compared with one SOC code (plan 8.17 step 4, T15.5).

The CV is read in memory and never stored. Its checks run in this order, and each can refuse:
AI is on (409 otherwise, before the file is read), the person's hourly AI limit, size, PDF or DOCX
by name, real content, virus scan, readable text. Only then are contact details taken out and
Claude asked for the comparison.
"""

from __future__ import annotations

import asyncio
import io
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import select

from app.ai.service import ai_ready, check_ai_limit
from app.core.errors import AppError, NotFoundError
from app.modules.files.validation import ALLOWED, extension_of, safe_filename, sniff
from app.modules.rbac.deps import Access, require
from app.modules.soc.cv import CvUnreadableError, extract_text, strip_contact_details
from app.modules.soc.cv_match import DISCLAIMER, match_cv
from app.modules.soc.models import SocUnitGroup
from app.modules.soc.ranking import is_low

router = APIRouter(tags=["soc"])
Matcher = Annotated[Access, Depends(require("soc.check.run"))]
MAX_CV_BYTES = 10 * 1024 * 1024
CV_KINDS = ("pdf", "docx")
SOC_CODE = Annotated[str, Form(pattern=r"^[1-9][0-9]{3}$")]
JOB = Annotated[str, Form(max_length=4000)]


class SocCvEvidenceOut(BaseModel):
    quote: str  # copied from the CV, word for word
    point: str


class SocCvMatchOut(BaseModel):
    soc_code: str
    title: str
    score: int  # 0-100: how fully the CV shows the occupation's duties
    low_confidence: bool  # true under 60: check with an adviser or CASCOT
    evidence: list[SocCvEvidenceOut]
    gaps: list[str]
    suggestions: list[str]
    removed: list[str]  # contact details taken out before sending: link, email, phone, ...
    disclaimer: str


@router.post("/soc/resume-match", response_model=SocCvMatchOut)
async def resume_match(
    request: Request,
    access: Matcher,
    cv: UploadFile,
    soc_code: SOC_CODE,
    job_description: JOB = "",
) -> SocCvMatchOut:
    if not await ai_ready(request, access):
        raise AppError("AI_UNAVAILABLE", "AI features are turned off.", status_code=409)
    # Before the file is read: scanning and text extraction are the costly part (C6.1.8).
    await check_ai_limit(request, access)
    data = await cv.read(MAX_CV_BYTES + 1)
    if len(data) > MAX_CV_BYTES:
        raise AppError("PAYLOAD_TOO_LARGE", "That CV is larger than 10 MB.", status_code=413)
    if not data:
        raise AppError("FILE_EMPTY", "That file is empty.", status_code=422)
    kind = ALLOWED.get(extension_of(safe_filename(cv.filename)), ("", ""))[0]
    if kind not in CV_KINDS:
        raise AppError("FILE_TYPE_NOT_ALLOWED", "Upload the CV as a PDF or DOCX.", status_code=422)
    if sniff(io.BytesIO(data)) != kind:
        raise AppError(
            "FILE_TYPE_MISMATCH",
            "The file is not what its name says it is, so it was not accepted.",
            status_code=415,
        )
    verdict = await request.app.state.files.scanner.scan(io.BytesIO(data))
    if verdict.status == "infected":
        raise AppError(
            "FILE_INFECTED",
            "A virus was found in that file, so it was not accepted.",
            status_code=422,
        )
    if verdict.status != "clean":
        raise AppError(
            "SCAN_UNAVAILABLE",
            "We could not check that file for viruses just now, so it was not accepted.",
            status_code=503,
        )
    try:
        text = await asyncio.to_thread(extract_text, data, kind)
    except CvUnreadableError as exc:
        raise AppError(
            "CV_NOT_READABLE",
            "We could not read text from that CV. Try a file with selectable text.",
            status_code=422,
        ) from exc
    stripped = strip_contact_details(text)
    unit = (
        await access.db.execute(select(SocUnitGroup).where(SocUnitGroup.code == soc_code))
    ).scalar_one_or_none()
    if unit is None:
        raise NotFoundError("We could not find that SOC code.")
    reply = await match_cv(
        request,
        access,
        code=unit.code,
        title=unit.title,
        description=unit.description,
        tasks=list(unit.tasks),
        job_description=job_description,
        cv_text=stripped.cleaned,
    )
    return SocCvMatchOut(
        soc_code=unit.code,
        title=unit.title,
        score=reply.score,
        low_confidence=is_low(reply.score),
        evidence=[SocCvEvidenceOut(quote=e.quote, point=e.point) for e in reply.evidence],
        gaps=reply.gaps,
        suggestions=reply.suggestions,
        removed=list(stripped.removed),
        disclaimer=DISCLAIMER,
    )
