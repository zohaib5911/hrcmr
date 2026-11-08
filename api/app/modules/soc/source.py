"""Reads the ONS SOC 2020 workbooks into rows (plan 6.10, T15.1).

Pure parsing: no database and no network. ``data/import_soc.py`` fetches the files and checks their
SHA-256 against a sidecar; ``importer.py`` loads what ``load_source`` returns. Anything unexpected
(a missing column, a code that is not four digits, a duplicate) stops the load with a ValueError, so
a half-understood file never reaches the database.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import openpyxl

if TYPE_CHECKING:
    from pathlib import Path

INDEX_SHEET = "SOC2020 coding index"
UNIT_GROUP_SHEET = "SOC2020 descriptions"
# The ONS writes this in the code column of its "see" cross-references (no occupation code).
CROSS_REFERENCE_MARKER = "}}}}"
BLANK_MARKER = "<blank>"
CODE = re.compile(r"[1-9][0-9]{3}")


@dataclass(frozen=True)
class IndexRow:
    index_title: str
    qualifier_add: str
    qualifier_ind: str
    soc_code: str


@dataclass(frozen=True)
class UnitGroupRow:
    code: str
    title: str
    description: str
    entry_requirements: str
    tasks: tuple[str, ...]
    typical_titles: tuple[str, ...]


@dataclass(frozen=True)
class SocSource:
    unit_groups: tuple[UnitGroupRow, ...]
    index_entries: tuple[IndexRow, ...]
    cross_references: int


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    return "" if text == BLANK_MARKER else text


def _bullets(text: str) -> tuple[str, ...]:
    """The ONS lists tasks and job titles one per line, each starting with a "~" marker."""
    items = (line.strip().removeprefix("~").strip() for line in text.splitlines())
    return tuple(item for item in items if item)


def _is_blank(row: tuple[object, ...]) -> bool:
    return all(_text(value) == "" for value in row)


def _columns(header: tuple[object, ...], wanted: tuple[str, ...]) -> dict[str, int]:
    # Headers can wrap onto two lines in the ONS file ("SOC2020\nGroup Title"), so compare words.
    found = {" ".join(_text(name).split()): index for index, name in enumerate(header)}
    missing = [name for name in wanted if name not in found]
    if missing:
        raise ValueError(f"missing columns: {', '.join(missing)}")
    return {name: found[name] for name in wanted}


def _sheet(path: Path, name: str) -> tuple[tuple[object, ...], list[tuple[object, ...]]]:
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        if name not in workbook.sheetnames:
            raise ValueError(f"{path.name}: no sheet named {name!r}")
        rows = [tuple(row) for row in workbook[name].iter_rows(values_only=True)]
    finally:
        workbook.close()
    if not rows:
        raise ValueError(f"{path.name}: sheet {name!r} is empty")
    # A short row (trailing empty cells dropped) reads as blank cells, not as an IndexError.
    width = len(rows[0])
    return rows[0], [row + (None,) * (width - len(row)) for row in rows[1:]]


def _index_entries(path: Path) -> tuple[tuple[IndexRow, ...], int]:
    header, rows = _sheet(path, INDEX_SHEET)
    col = _columns(header, ("INDEXOCC", "ADD", "IND", "SOC_2020"))
    entries: list[IndexRow] = []
    seen: set[IndexRow] = set()
    cross_references = 0
    for number, row in enumerate(rows, start=2):
        if _is_blank(row):
            continue
        code = _text(row[col["SOC_2020"]])
        if code == CROSS_REFERENCE_MARKER:
            cross_references += 1
            continue
        title = _text(row[col["INDEXOCC"]])
        if not CODE.fullmatch(code):
            raise ValueError(f"index row {number}: {code!r} is not a four-digit SOC code")
        if not title:
            raise ValueError(f"index row {number}: no index title")
        entry = IndexRow(
            index_title=title,
            qualifier_add=_text(row[col["ADD"]]),
            qualifier_ind=_text(row[col["IND"]]),
            soc_code=code,
        )
        if entry in seen:
            raise ValueError(f"index row {number}: duplicate entry for {title!r} ({code})")
        seen.add(entry)
        entries.append(entry)
    return tuple(entries), cross_references


def _unit_groups(path: Path) -> tuple[UnitGroupRow, ...]:
    header, rows = _sheet(path, UNIT_GROUP_SHEET)
    col = _columns(
        header,
        (
            "SOC2020 Unit Group",
            "SOC2020 Group Title",
            "Group Description",
            "Typical Entry Routes And Associated Qualifications",
            "Tasks",
            "Related Job Titles",
        ),
    )
    groups: list[UnitGroupRow] = []
    seen: set[str] = set()
    for number, row in enumerate(rows, start=2):
        # Major, sub-major and minor group rows have no unit group code; only unit groups load.
        code = _text(row[col["SOC2020 Unit Group"]])
        if not code:
            continue
        if not CODE.fullmatch(code):
            raise ValueError(f"unit group row {number}: {code!r} is not a four-digit SOC code")
        if code in seen:
            raise ValueError(f"unit group row {number}: {code} appears twice")
        seen.add(code)
        entry_route = "Typical Entry Routes And Associated Qualifications"
        group = UnitGroupRow(
            code=code,
            title=_text(row[col["SOC2020 Group Title"]]),
            description=_text(row[col["Group Description"]]),
            entry_requirements=_text(row[col[entry_route]]),
            tasks=_bullets(_text(row[col["Tasks"]])),
            typical_titles=_bullets(_text(row[col["Related Job Titles"]])),
        )
        if not (group.title and group.description and group.entry_requirements):
            raise ValueError(f"unit group {code}: title, description or entry route is blank")
        if not (group.tasks and group.typical_titles):
            raise ValueError(f"unit group {code}: no tasks or related job titles")
        groups.append(group)
    return tuple(groups)


def load_source(index_path: Path, unit_group_path: Path) -> SocSource:
    """Parses both workbooks. Every index code must be a unit group, so the foreign key holds."""
    unit_groups = _unit_groups(unit_group_path)
    index_entries, cross_references = _index_entries(index_path)
    known = {group.code for group in unit_groups}
    unknown = sorted({entry.soc_code for entry in index_entries} - known)
    if unknown:
        raise ValueError(f"index codes with no unit group: {', '.join(unknown)}")
    return SocSource(
        unit_groups=unit_groups,
        index_entries=index_entries,
        cross_references=cross_references,
    )


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_against_sidecar(path: Path, sidecar: Path) -> None:
    """Raises when the file is not the one its sidecar (source URL, bytes, SHA-256) describes."""
    record = json.loads(sidecar.read_text(encoding="utf-8"))
    actual = sha256_of(path)
    if actual != record["sha256"]:
        raise ValueError(f"{path.name} does not match {sidecar.name} (SHA-256 {actual})")
