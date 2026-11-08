"""Candidate retrieval for the SOC checker (plan 8.17 steps 2a-2b, T15.4).

Three searches run in the database: trigram similarity and full-text over the ONS index titles,
and vector distance over the local embeddings (index titles and unit-group text). Each search
ranks its own list of unit-group codes; reciprocal rank fusion merges them into one list of the
best ``CANDIDATES`` codes, so no single search decides on its own.
"""

from __future__ import annotations

import asyncio
import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.modules.soc.models import SocIndexEntry, SocUnitGroup

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.soc.importer import Embedder

CANDIDATES = 10  # the codes the search returns, and the codes the AI ranks
LEG = 30  # how many hits each search contributes before fusion
RRF_K = 60  # the usual reciprocal-rank-fusion constant
DESCRIPTION_CHARS = 1000  # how much of a job description goes into the vector query
_NON_WORD = re.compile(r"[^\w\s]")


@dataclass(frozen=True)
class Candidate:
    code: str
    title: str  # the unit group's title
    description: str
    tasks: tuple[str, ...]
    typical_titles: tuple[str, ...]
    matched_title: str  # the index title (or unit-group title) that found this code first


def normalise_title(text: str) -> str:
    """Unicode form, case, punctuation and spacing folded: "Nurse, Registered" becomes "nurse
    registered"."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(_NON_WORD.sub(" ", folded).split())


Hit = tuple[str, str]  # (soc code, the title that matched)


def fuse(legs: Sequence[Sequence[Hit]], limit: int = CANDIDATES) -> list[tuple[str, str]]:
    """Reciprocal rank fusion. Each leg is best-first. Returns (code, matched title), best first.

    A code scores 1 / (RRF_K + rank) in every leg it appears in, so a code that several searches
    agree on beats one that only a single search likes. Ties break on the code, so the order is
    the same on every run. The title kept is the one from the first leg that found the code.
    """
    scores: dict[str, float] = {}
    matched: dict[str, str] = {}
    for leg in legs:
        rank = 0
        seen: set[str] = set()
        for code, title in leg:
            if code in seen:
                continue
            seen.add(code)
            rank += 1
            scores[code] = scores.get(code, 0.0) + 1.0 / (RRF_K + rank)
            matched.setdefault(code, title)
    ordered = sorted(scores, key=lambda code: (-scores[code], code))[:limit]
    return [(code, matched[code]) for code in ordered]


async def query_vector(embed: Embedder, text: str) -> list[float]:
    """The embedding of one query. The model runs in a thread, so the event loop is not blocked."""
    vectors = await asyncio.to_thread(embed, [text])
    return vectors[0]


async def retrieve(
    db: AsyncSession, title: str, vector: list[float], limit: int = CANDIDATES
) -> list[Candidate]:
    """The best ``limit`` unit groups for a normalised job title and its query vector."""
    similarity = func.similarity(SocIndexEntry.index_title, title)
    trigram = await db.execute(
        select(SocIndexEntry.soc_code, SocIndexEntry.index_title)
        .where(SocIndexEntry.index_title.op("%")(title))
        .order_by(similarity.desc(), SocIndexEntry.soc_code)
        .limit(LEG)
    )
    document = func.to_tsvector("english", SocIndexEntry.index_title)
    query = func.plainto_tsquery("english", title)
    full_text = await db.execute(
        select(SocIndexEntry.soc_code, SocIndexEntry.index_title)
        .where(document.op("@@")(query))
        .order_by(func.ts_rank(document, query).desc(), SocIndexEntry.soc_code)
        .limit(LEG)
    )
    by_index = await db.execute(
        select(SocIndexEntry.soc_code, SocIndexEntry.index_title)
        .order_by(SocIndexEntry.embedding.cosine_distance(vector), SocIndexEntry.soc_code)
        .limit(LEG)
    )
    by_group = await db.execute(
        select(SocUnitGroup.code, SocUnitGroup.title)
        .order_by(SocUnitGroup.embedding.cosine_distance(vector), SocUnitGroup.code)
        .limit(LEG)
    )
    legs = [
        [(row[0], row[1]) for row in result.all()]
        for result in (trigram, full_text, by_index, by_group)
    ]
    fused = fuse(legs, limit)
    if not fused:
        return []
    groups = {
        group.code: group
        for group in (
            await db.execute(
                select(SocUnitGroup).where(SocUnitGroup.code.in_([code for code, _ in fused]))
            )
        )
        .scalars()
        .all()
    }
    return [
        Candidate(
            code=code,
            title=groups[code].title,
            description=groups[code].description,
            tasks=tuple(groups[code].tasks),
            typical_titles=tuple(groups[code].typical_titles),
            matched_title=matched_title,
        )
        for code, matched_title in fused
    ]
