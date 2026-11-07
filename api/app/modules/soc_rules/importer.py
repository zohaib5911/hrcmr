"""Writes parsed GOV.UK rules pages into a draft ``rules_versions`` row (plan 6.10 and 8.17, T15.2).

The import never changes what the checker uses: it adds a **draft** with its own copy of every rate,
list entry and salary rule, plus a diff against the live version for a person to review. Only
``publish_rules_version`` makes a draft live (the owner runs it once they approve the diff; the
super-admin screen in T15.7 calls the same function). Publishing also sets
``soc_unit_groups.rqf_level`` from the published tables.

Re-runnable: pages whose hashes match the newest version add nothing; a newer import replaces an
unpublished draft, so there is never more than one draft waiting.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, insert, select, update

from app.db.ids import uuid7
from app.modules.soc.models import SocUnitGroup
from app.modules.soc_rules.models import (
    GoingRate,
    IneligibleCode,
    PayScaleRate,
    RulesVersion,
    SalaryRule,
    ShortageListEntry,
)

if TYPE_CHECKING:
    import uuid
    from collections.abc import Iterable, Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.soc_rules.source import RulesSource

BATCH = 500
# SW 29.1A: dependants only when the job is in Table 1, 2 or 3 of Appendix Skilled Occupations.
DEPENDANT_TABLES = ("1", "2", "3")
# The notes under each table state its skill level (RQF). Checked against the notes at publish.
RQF_BY_TABLE = {"1": "6", "3": "6", "1a": "3-5", "2aa": "3-5", "3a": "3-5", "2a": "below"}
RQF_NOTE = {
    "1": "level 6 or above",
    "3": "level 6 or above",
    "1a": "level 3-5",
    "2aa": "level 3-5",
    "3a": "level 3-5",
    "2a": "below RQF level 3",
}
RQF2_EXCEPTION = re.compile(
    r"other than “(\d{4}) [^”]+”, which is considered to be skilled to RQF level 2"
)


class RulesImportError(ValueError):
    """A publish or import that must not go ahead (wrong status, notes changed)."""


@dataclass(frozen=True)
class ImportResult:
    version_id: uuid.UUID | None  # None when nothing changed
    unchanged: bool
    replaced_draft: bool
    diff_summary: dict[str, Any]
    counts: dict[str, int]


# ---------------------------------------------------------------------------------------------
# Rows


def _going_rows(version: uuid.UUID, source: RulesSource) -> list[dict[str, Any]]:
    return [
        {
            "rules_version_id": version,
            "soc_code": r.soc_code,
            "table": r.table,
            "title": r.title,
            "administration": r.administration,
            "related_titles": list(r.related_titles),
            "soc2010_codes": list(r.soc2010_codes),
            "annual_rate": r.annual_rate,
            "hourly_rate": r.hourly_rate,
            "rate_90": r.rate_90,
            "rate_80": r.rate_80,
            "rate_70": r.rate_70,
            "phd_points_eligible": r.phd_points_eligible,
            "basis_hours": r.basis_hours,
            "notes": r.notes,
        }
        for r in source.going_rates
    ]


def _pay_rows(version: uuid.UUID, source: RulesSource) -> list[dict[str, Any]]:
    return [
        {
            "rules_version_id": version,
            "source_table": r.source_table,
            "soc_code": r.soc_code,
            "administration": r.administration,
            "band_or_role": r.band_or_role,
            "annual_rate": r.annual_rate,
            "basis_hours": r.basis_hours,
        }
        for r in source.pay_scales
    ]


def _ineligible_rows(version: uuid.UUID, source: RulesSource) -> list[dict[str, Any]]:
    return [
        {
            "rules_version_id": version,
            "soc_code": r.soc_code,
            "title": r.title,
            "related_titles": list(r.related_titles),
            "reason": r.reason,
        }
        for r in source.ineligible
    ]


def _shortage_rows(version: uuid.UUID, source: RulesSource) -> list[dict[str, Any]]:
    with_dependants = {r.soc_code for r in source.going_rates if r.table in DEPENDANT_TABLES}
    return [
        {
            "rules_version_id": version,
            "list_name": r.list_name,
            "soc_code": r.soc_code,
            "title": r.title,
            "condition_text": r.condition_text,
            "job_types": list(r.job_types),
            "nations": list(r.nations),
            "removal_date": r.removal_date,
            "dependants_allowed": r.soc_code in with_dependants,
        }
        for r in source.shortage
    ]


def _salary_rows(version: uuid.UUID, source: RulesSource) -> list[dict[str, Any]]:
    return [
        {
            "rules_version_id": version,
            "option": r.option,
            "general_threshold": r.general_threshold,
            "going_rate_pct": r.going_rate_pct,
            "criteria_key": r.criteria_key,
            "applies_to": r.applies_to,
            "requirement_text": r.requirement_text,
            "further_rules": r.further_rules,
        }
        for r in source.salary_rules
    ]


async def _insert(db: AsyncSession, model: type[Any], rows: Sequence[dict[str, Any]]) -> None:
    for start in range(0, len(rows), BATCH):
        await db.execute(insert(model), list(rows[start : start + BATCH]))


# ---------------------------------------------------------------------------------------------
# Diff against the live version


def _money(value: Decimal | None) -> str | None:
    return None if value is None else f"{value:.2f}"


def _keyed(
    rows: Iterable[dict[str, Any]], key: Sequence[str], fields: Sequence[str]
) -> dict[str, dict[str, Any]]:
    return {
        "|".join(str(row[k] or "") for k in key): {
            f: _money(row[f]) if isinstance(row[f], Decimal) else row[f] for f in fields
        }
        for row in rows
    }


def _compare(old: dict[str, dict[str, Any]], new: dict[str, dict[str, Any]]) -> dict[str, Any]:
    changed = [
        {"key": key, "field": field, "from": old[key][field], "to": value}
        for key in sorted(old.keys() & new.keys())
        for field, value in new[key].items()
        if old[key][field] != value
    ]
    return {
        "added": sorted(new.keys() - old.keys()),
        "removed": sorted(old.keys() - new.keys()),
        "changed": changed,
    }


_RATE_FIELDS = (
    "annual_rate",
    "hourly_rate",
    "rate_90",
    "rate_80",
    "rate_70",
    "phd_points_eligible",
)
_SECTIONS: dict[str, tuple[Sequence[str], Sequence[str]]] = {
    "going_rates": (("table", "soc_code", "administration"), (*_RATE_FIELDS, "basis_hours")),
    "pay_scale_rates": (
        ("source_table", "soc_code", "administration", "band_or_role"),
        ("annual_rate", "basis_hours"),
    ),
    "ineligible_codes": (("soc_code",), ("title",)),
    "shortage_list_entries": (
        ("list_name", "soc_code"),
        ("condition_text", "job_types", "nations", "removal_date", "dependants_allowed"),
    ),
    "salary_rules": (
        ("option",),
        ("general_threshold", "going_rate_pct", "criteria_key", "applies_to"),
    ),
}
_MODELS: dict[str, type[Any]] = {
    "going_rates": GoingRate,
    "pay_scale_rates": PayScaleRate,
    "ineligible_codes": IneligibleCode,
    "shortage_list_entries": ShortageListEntry,
    "salary_rules": SalaryRule,
}


async def _rows_of(db: AsyncSession, name: str, version: uuid.UUID) -> list[dict[str, Any]]:
    model = _MODELS[name]
    key, fields = _SECTIONS[name]
    columns = [getattr(model, f) for f in (*key, *fields)]
    result = await db.execute(select(*columns).where(model.rules_version_id == version))
    return [dict(zip((*key, *fields), row, strict=True)) for row in result.all()]


def _jsonable(value: Any) -> Any:
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    return value


async def _diff(
    db: AsyncSession, live: RulesVersion | None, new_rows: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    counts = {name: len(rows) for name, rows in new_rows.items()}
    if live is None:
        return {"against": None, "counts": counts, "note": "No live version: everything is new."}
    sections: dict[str, Any] = {}
    for name, (key, fields) in _SECTIONS.items():
        old = _keyed(await _rows_of(db, name, live.id), key, fields)
        new = _keyed(new_rows[name], key, fields)
        compared = _compare(old, new)
        for change in compared["changed"]:
            change["from"], change["to"] = _jsonable(change["from"]), _jsonable(change["to"])
        sections[name] = compared
    return {
        "against": {"id": str(live.id), "name": live.name},
        "counts": counts,
        "sections": sections,
        "has_changes": any(any(s.values()) for s in sections.values()),
    }


# ---------------------------------------------------------------------------------------------
# Import and publish


async def _newest(db: AsyncSession) -> RulesVersion | None:
    result = await db.execute(
        select(RulesVersion).order_by(RulesVersion.created_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()


def _hashes(source_urls: Sequence[dict[str, Any]]) -> set[str]:
    return {str(page["sha256"]) for page in source_urls}


async def import_rules_source(db: AsyncSession, source: RulesSource) -> ImportResult:
    """Adds a draft version from ``source`` in the caller's transaction. The caller commits."""
    pages = [page.as_json() for page in source.pages]
    newest = await _newest(db)
    if newest is not None and _hashes(newest.source_urls) == _hashes(pages):
        return ImportResult(None, True, False, newest.diff_summary, {})

    drafts = await db.execute(delete(RulesVersion).where(RulesVersion.status == "draft"))
    live = (
        await db.execute(select(RulesVersion).where(RulesVersion.status == "live"))
    ).scalar_one_or_none()

    version_id = uuid7()
    rows = {
        "going_rates": _going_rows(version_id, source),
        "pay_scale_rates": _pay_rows(version_id, source),
        "ineligible_codes": _ineligible_rows(version_id, source),
        "shortage_list_entries": _shortage_rows(version_id, source),
        "salary_rules": _salary_rows(version_id, source),
    }
    diff = await _diff(db, live, rows)
    db.add(
        RulesVersion(
            id=version_id,
            name=f"Immigration Rules as updated {source.effective_from:%-d %B %Y}",
            status="draft",
            source_urls=pages,
            effective_from=source.effective_from,
            diff_summary=diff,
            table_notes=source.table_notes,
        )
    )
    await db.flush()
    for name, model in _MODELS.items():
        await _insert(db, model, rows[name])
    return ImportResult(
        version_id=version_id,
        unchanged=False,
        replaced_draft=bool(getattr(drafts, "rowcount", 0)),
        diff_summary=diff,
        counts={name: len(r) for name, r in rows.items()},
    )


def rqf_levels(
    going_codes: Iterable[tuple[str, str]], table_notes: dict[str, str]
) -> dict[str, str]:
    """Code -> RQF level from the tables a code appears in, checked against each table's notes."""
    for table, phrase in RQF_NOTE.items():
        if phrase not in table_notes.get(table, ""):
            raise RulesImportError(f"Table {table} notes no longer say {phrase!r}")
    below = {m.group(1) for m in RQF2_EXCEPTION.finditer(" ".join(table_notes.values()))}
    rank = {"6": 3, "3-5": 2, "below": 1}
    levels: dict[str, str] = {}
    for table, code in going_codes:
        level = RQF_BY_TABLE.get(table)
        if level is None:
            continue
        if level == "3-5" and code in below:
            level = "below"
        if rank[level] > rank.get(levels.get(code, ""), 0):
            levels[code] = level
    return levels


async def publish_rules_version(
    db: AsyncSession, version_id: uuid.UUID, published_by: uuid.UUID | None = None
) -> None:
    """Draft -> live; the previous live version -> retired; RQF levels follow the new tables.
    In the caller's transaction. Saved checks keep their own version id, so nothing else moves."""
    version = await db.get(RulesVersion, version_id, with_for_update=True)
    if version is None or version.status != "draft":
        raise RulesImportError("Only a draft rules version can be published.")
    await _make_live(db, version, published_by)


async def rollback_rules_version(
    db: AsyncSession, version_id: uuid.UUID, published_by: uuid.UUID | None = None
) -> None:
    """Retired -> live again, and the live version -> retired (T15.7). The same RQF levels as the
    restored tables give. In the caller's transaction."""
    version = await db.get(RulesVersion, version_id, with_for_update=True)
    if version is None or version.status != "retired":
        raise RulesImportError("Only a retired rules version can be restored.")
    await _make_live(db, version, published_by)


async def _make_live(
    db: AsyncSession, version: RulesVersion, published_by: uuid.UUID | None
) -> None:
    going = await db.execute(
        select(GoingRate.table, GoingRate.soc_code).where(GoingRate.rules_version_id == version.id)
    )
    levels = rqf_levels([(t, c) for t, c in going.all()], version.table_notes)

    await db.execute(
        update(RulesVersion).where(RulesVersion.status == "live").values(status="retired")
    )
    version.status = "live"
    version.published_at = dt.datetime.now(dt.UTC)
    version.published_by = published_by
    await db.flush()

    await db.execute(update(SocUnitGroup).values(rqf_level=None))
    for level in ("6", "3-5", "below"):
        codes = [code for code, value in levels.items() if value == level]
        if codes:
            await db.execute(
                update(SocUnitGroup).where(SocUnitGroup.code.in_(codes)).values(rqf_level=level)
            )
