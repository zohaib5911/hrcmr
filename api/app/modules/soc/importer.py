"""Loads SOC 2020 rows into ``soc_unit_groups`` and ``soc_index_entries`` (plan 6.10, T15.1).

Re-runnable: each row is matched on its natural key (the unit group code; the index title,
qualifiers and code) and updated in place, so a second run adds no rows. Unit groups load first,
because index entries reference them. Each row gets an embedding of its own text, computed by an
injected function: the real one is local (fastembed); tests pass a fake, so nothing downloads.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.modules.soc.models import EMBEDDING_DIMENSIONS, SocIndexEntry, SocUnitGroup

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.soc.source import IndexRow, SocSource, UnitGroupRow

MODEL_NAME = "BAAI/bge-small-en-v1.5"  # 384 dimensions, matches EMBEDDING_DIMENSIONS
BATCH = 500

Embedder = Callable[[Sequence[str]], list[list[float]]]


@dataclass(frozen=True)
class ImportCounts:
    unit_groups: int
    index_entries: int
    cross_references_skipped: int
    unit_groups_in_table: int
    index_entries_in_table: int


def fastembed_embedder() -> Embedder:
    """The local embedding model. fastembed downloads its weights the first time it runs."""
    from fastembed import TextEmbedding

    model = TextEmbedding(model_name=MODEL_NAME)

    def embed(texts: Sequence[str]) -> list[list[float]]:
        return [vector.tolist() for vector in model.embed(list(texts))]

    return embed


def unit_group_text(row: UnitGroupRow) -> str:
    return " ".join([row.title, row.description, *row.tasks, *row.typical_titles])


def index_text(row: IndexRow) -> str:
    qualifiers = " ".join(part for part in (row.qualifier_add, row.qualifier_ind) if part)
    return f"{row.index_title} {qualifiers}".strip()


async def _embed_all(embed: Embedder, texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH):
        # The model is CPU-bound, so it runs in a thread rather than blocking the event loop.
        vectors.extend(await asyncio.to_thread(embed, texts[start : start + BATCH]))
    if len(vectors) != len(texts) or any(len(v) != EMBEDDING_DIMENSIONS for v in vectors):
        raise ValueError(
            f"embedder returned {len(vectors)} vectors for {len(texts)} rows, "
            f"expected {EMBEDDING_DIMENSIONS} dimensions each"
        )
    return vectors


async def _upsert_unit_groups(
    db: AsyncSession, groups: Sequence[UnitGroupRow], vectors: Sequence[list[float]]
) -> None:
    # rqf_level is not written here: the rules-data importer (T15.2) owns it.
    for start in range(0, len(groups), BATCH):
        values = [
            {
                "code": group.code,
                "title": group.title,
                "description": group.description,
                "tasks": list(group.tasks),
                "entry_requirements": group.entry_requirements,
                "typical_titles": list(group.typical_titles),
                "embedding": vector,
            }
            for group, vector in zip(
                groups[start : start + BATCH], vectors[start : start + BATCH], strict=True
            )
        ]
        statement = insert(SocUnitGroup).values(values)
        statement = statement.on_conflict_do_update(
            index_elements=[SocUnitGroup.code],
            set_={
                name: statement.excluded[name]
                for name in (
                    "title",
                    "description",
                    "tasks",
                    "entry_requirements",
                    "typical_titles",
                    "embedding",
                )
            },
        )
        await db.execute(statement)


async def _upsert_index_entries(
    db: AsyncSession, entries: Sequence[IndexRow], vectors: Sequence[list[float]]
) -> None:
    for start in range(0, len(entries), BATCH):
        values = [
            {
                "index_title": entry.index_title,
                "qualifier_add": entry.qualifier_add,
                "qualifier_ind": entry.qualifier_ind,
                "soc_code": entry.soc_code,
                "embedding": vector,
            }
            for entry, vector in zip(
                entries[start : start + BATCH], vectors[start : start + BATCH], strict=True
            )
        ]
        statement = insert(SocIndexEntry).values(values)
        statement = statement.on_conflict_do_update(
            index_elements=[
                SocIndexEntry.index_title,
                SocIndexEntry.qualifier_add,
                SocIndexEntry.qualifier_ind,
                SocIndexEntry.soc_code,
            ],
            set_={"embedding": statement.excluded["embedding"]},
        )
        await db.execute(statement)


async def load_soc_source(db: AsyncSession, source: SocSource, embed: Embedder) -> ImportCounts:
    """Writes the parsed source in the caller's transaction. The caller commits."""
    group_vectors = await _embed_all(embed, [unit_group_text(g) for g in source.unit_groups])
    await _upsert_unit_groups(db, source.unit_groups, group_vectors)
    entry_vectors = await _embed_all(embed, [index_text(e) for e in source.index_entries])
    await _upsert_index_entries(db, source.index_entries, entry_vectors)
    groups_total = await db.scalar(select(func.count()).select_from(SocUnitGroup))
    entries_total = await db.scalar(select(func.count()).select_from(SocIndexEntry))
    return ImportCounts(
        unit_groups=len(source.unit_groups),
        index_entries=len(source.index_entries),
        cross_references_skipped=source.cross_references,
        unit_groups_in_table=int(groups_total or 0),
        index_entries_in_table=int(entries_total or 0),
    )
