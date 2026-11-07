"""Claude compares a CV with one SOC code and the job (plan 8.17 step 4, T15.5).

Claude returns JSON: a score from 0 to 100, evidence quoted from the CV, gaps, and suggestions. The
prompt carries the guardrails from the plan: suggestions describe the genuine job and never reword
its duties to reach another code, and the CV is never the source of an invented quote. A quote that
does not appear word for word in the CV is dropped before anything is shown.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, ValidationError

from app.ai.service import generate
from app.core.errors import AppError

if TYPE_CHECKING:
    from fastapi import Request

    from app.modules.rbac.deps import Access

DISCLAIMER = "General guidance, not legal or immigration advice."

TASK = (
    "Task: compare one candidate's CV with one UK SOC 2020 occupation and with one job "
    "description. The data gives the occupation (code, title, official description and tasks), "
    "the job description and the CV text. Contact details were removed from the CV: leave the "
    "placeholders such as [email removed] as they are. Answer with JSON only and no other text, "
    'in this shape: {"score": 0-100, "evidence": [{"quote": "words copied exactly from the CV", '
    '"point": "the duty or skill the quote shows"}], "gaps": ["a duty or qualification the CV '
    'does not show"], '
    '"suggestions": ["a practical step"]}. '
    "The score is how fully the CV shows the occupation's duties: 0 for none, 100 for all. "
    "Quote only words that appear in the CV, copied exactly. Never invent a quote, a job, a "
    "qualification, a date or a skill. "
    "Suggestions must describe the genuine job. Never suggest rewording, inflating or changing the "
    "job's duties to reach a different or higher-paid code or an eligibility route; if the user "
    "asks for that, say that misdescribing a role risks the sponsor licence. "
    "Do not write any names or contact details."
)


class EvidenceItem(BaseModel):
    quote: str = Field(min_length=1, max_length=400)
    point: str = Field(default="", max_length=300)


class CvReply(BaseModel):
    score: int = Field(ge=0, le=100)
    evidence: list[EvidenceItem] = Field(default_factory=list, max_length=8)
    gaps: list[str] = Field(default_factory=list, max_length=8)
    suggestions: list[str] = Field(default_factory=list, max_length=6)


def _squash(text: str) -> str:
    """Case and spacing folded, so a quote still matches when the line breaks fall differently."""
    return " ".join(text.casefold().split())


def parse_cv_reply(reply: str, cv_text: str) -> CvReply | None:
    """The reply as a CvReply, without any quote that is not in the CV; None if unreadable."""
    text = reply.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        parsed = CvReply.model_validate(json.loads(text))
    except (ValueError, ValidationError):
        return None
    cv = _squash(cv_text)
    evidence = [item for item in parsed.evidence if (quote := _squash(item.quote)) and quote in cv]
    return parsed.model_copy(update={"evidence": evidence})


async def match_cv(
    request: Request,
    access: Access,
    *,
    code: str,
    title: str,
    description: str,
    tasks: list[str],
    job_description: str,
    cv_text: str,
) -> CvReply:
    """Claude's comparison. There is no non-AI fallback, so an unusable answer is an error."""
    data = {
        "occupation": {"code": code, "title": title, "description": description, "tasks": tasks},
        "job_description": job_description,
        "cv_text": cv_text,
    }
    reply = await generate(
        request,
        access,
        feature="soc_cv",
        task=TASK,
        instruction="Compare the CV with the occupation and the job description.",
        data=data,
        fast=False,
        max_tokens=1500,
    )
    parsed = parse_cv_reply(reply, cv_text)
    if parsed is None:
        raise AppError("AI_FAILED", "The AI could not compare the CV. Try again.", status_code=502)
    return parsed
