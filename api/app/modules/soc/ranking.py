"""Claude re-ranks the retrieved candidates (plan 8.17 step 2c, T15.4).

Claude sees the job title and description and each candidate's official description, tasks and
typical titles. It answers with JSON only: the candidate codes, best first, each with a confidence
from 0 to 100, the duties that matched, and a reason (why it fits, or why it ranks lower). The
reply is checked strictly. When the AI is off, unavailable, or answers something unreadable, the
search order is returned instead, with ``ai_ranked`` false and no confidence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, ValidationError

from app.ai.service import ai_ready, generate
from app.core.errors import AppError

if TYPE_CHECKING:
    from fastapi import Request

    from app.modules.rbac.deps import Access
    from app.modules.soc.retrieval import Candidate

LOW_CONFIDENCE = 60  # below this the result is flagged for the user to check
FALLBACK_CODES = ("AI_FAILED", "RATE_LIMITED", "AI_UNAVAILABLE")
NOT_AI_RANKED = "Not AI-ranked: these are in search order, with no confidence."
REPLY_NOT_READ = "The AI reply could not be read, so these are in search order, not AI-ranked."

TASK = (
    "Task: rank the candidate SOC 2020 unit groups for one UK job. The data gives the job title, "
    "the job description and the candidates, each with a code, title, official description, tasks "
    "and typical titles. Judge by the duties: match what the job does against the candidate's "
    "tasks and description, not only the words in the title. Answer with JSON only and no other "
    'text, in this shape: {"ranking": [{"code": "2134", "confidence": 85, "matched_duties": '
    '["a duty from the job"], "reason": "for the first entry, why it fits; for the others, why it '
    'ranks lower"}]}. Use only the candidate codes given, each at most once, best first. '
    "Confidence is 0 to 100: how sure you are that this is the right code for this job. Do not "
    "invent duties, and do not write any names."
)


class RankedItem(BaseModel):
    code: str = Field(min_length=1, max_length=4)
    confidence: int = Field(ge=0, le=100)
    matched_duties: list[str] = Field(default_factory=list, max_length=12)
    reason: str = Field(default="", max_length=600)


class RankingReply(BaseModel):
    ranking: list[RankedItem] = Field(min_length=1, max_length=10)


@dataclass(frozen=True)
class Ranked:
    candidate: Candidate
    confidence: int | None  # None when the AI did not rank
    matched_duties: tuple[str, ...]
    reason: str | None


@dataclass(frozen=True)
class RankOutcome:
    items: list[Ranked]
    ai_ranked: bool
    notice: str | None
    low_confidence: bool = False


def is_low(confidence: int | None) -> bool:
    return confidence is not None and confidence < LOW_CONFIDENCE


def parse_ranking(reply: str, candidate_codes: set[str]) -> list[RankedItem] | None:
    """The ranking, or None when the reply is not the JSON we asked for.

    A code that is not one of the candidates, or that appears twice, makes the whole reply
    invalid: a half-trusted ranking is worse than the search order.
    """
    text = reply.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        data: Any = json.loads(text)
        parsed = RankingReply.model_validate(data)
    except (ValueError, ValidationError):
        return None
    codes = [item.code for item in parsed.ranking]
    if len(set(codes)) != len(codes) or not set(codes) <= candidate_codes:
        return None
    return parsed.ranking


def _unranked(candidates: list[Candidate], notice: str) -> RankOutcome:
    items = [
        Ranked(candidate=c, confidence=None, matched_duties=(), reason=None) for c in candidates
    ]
    return RankOutcome(items=items, ai_ranked=False, notice=notice)


def _data(job_title: str, job_description: str, candidates: list[Candidate]) -> dict[str, Any]:
    return {
        "job_title": job_title,
        "job_description": job_description,
        "candidates": [
            {
                "code": c.code,
                "title": c.title,
                "description": c.description,
                "tasks": list(c.tasks),
                "typical_titles": list(c.typical_titles),
            }
            for c in candidates
        ],
    }


async def rank(
    request: Request,
    access: Access,
    *,
    job_title: str,
    job_description: str,
    candidates: list[Candidate],
) -> RankOutcome:
    """Claude's ranking of the candidates, or the search order when AI cannot give one.

    The job text is redacted before it is sent, as for every AI feature (an e-mail address, for
    example, never leaves the server). A request that still holds personal data after redaction is
    refused with AI_REFUSED, and the caller answers 422.
    """
    if not candidates:
        return RankOutcome(items=[], ai_ranked=False, notice=None)
    if not await ai_ready(request, access):
        return _unranked(candidates, NOT_AI_RANKED)
    try:
        reply = await generate(
            request,
            access,
            feature="soc_match",
            task=TASK,
            instruction="Rank these candidate codes for the job.",
            data=_data(job_title, job_description, candidates),
            fast=False,
            max_tokens=1500,
        )
    except AppError as exc:
        if exc.code in FALLBACK_CODES:
            return _unranked(candidates, NOT_AI_RANKED)
        raise
    ranking = parse_ranking(reply, {c.code for c in candidates})
    if ranking is None:
        return _unranked(candidates, REPLY_NOT_READ)
    by_code = {c.code: c for c in candidates}
    items = [
        Ranked(
            candidate=by_code[item.code],
            confidence=item.confidence,
            matched_duties=tuple(item.matched_duties),
            reason=item.reason or None,
        )
        for item in ranking
    ]
    top = items[0].confidence
    return RankOutcome(items=items, ai_ranked=True, notice=None, low_confidence=is_low(top))
