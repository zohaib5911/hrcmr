"""T15.1: the SOC 2020 workbooks parse into the rows the importer loads, and anything unexpected stops
the load. Runs on the small sample copied from the ONS files; no network, no database."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import openpyxl
import pytest

from app.modules.soc.source import (
    INDEX_SHEET,
    UNIT_GROUP_SHEET,
    check_against_sidecar,
    load_source,
    sha256_of,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "soc"
INDEX_FILE = FIXTURES / "soc2020-coding-index-sample.xlsx"
UNIT_FILE = FIXTURES / "soc2020-unit-groups-sample.xlsx"
INDEX_HEADER = ["UNIQUE ID", "SOC_2020", "INDEXOCC", "ADD", "IND"]
UNIT_HEADER = [
    "UNIQUE ID",
    "SOC2020 Unit Group",
    "SOC2020\nGroup Title",
    "Group Description",
    "Typical Entry Routes And Associated Qualifications",
    "Tasks",
    "Related Job Titles",
]


def _workbook(
    path: Path, sheet: str, header: Sequence[str], rows: Sequence[Sequence[object]]
) -> Path:
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    assert worksheet is not None
    worksheet.title = sheet
    worksheet.append(list(header))
    for row in rows:
        worksheet.append(list(row))
    workbook.save(path)
    return path


def _unit_row(code: object, title: str = "A group") -> list[object]:
    return [
        "soc-y1aa",
        code,
        title,
        "Describes the group.",
        "Entry by a relevant qualification.",
        "~ does the work\n~ checks the work",
        "~ Example job\n~ Another job",
    ]


def test_the_sample_parses_to_the_expected_counts() -> None:
    source = load_source(INDEX_FILE, UNIT_FILE)

    assert len(source.unit_groups) == 9
    assert len(source.index_entries) == 36
    assert source.cross_references == 3


def test_codes_are_four_digit_text_and_every_index_code_is_a_unit_group() -> None:
    source = load_source(INDEX_FILE, UNIT_FILE)
    groups = {group.code for group in source.unit_groups}

    assert all(group.code.isdigit() and len(group.code) == 4 for group in source.unit_groups)
    assert all(entry.soc_code in groups for entry in source.index_entries)
    # The ONS file stores some codes as numbers; they must arrive as "1111", not "1111.0".
    assert "1111" in groups


def test_tasks_and_related_titles_are_split_into_plain_items() -> None:
    group = next(g for g in load_source(INDEX_FILE, UNIT_FILE).unit_groups if g.code == "1111")

    assert group.title == "Chief executives and senior officials"
    assert len(group.tasks) == 9
    assert group.tasks[0].startswith("analyses economic")
    assert "Chairman" in group.typical_titles
    assert not any(item.startswith("~") for item in (*group.tasks, *group.typical_titles))


def test_hierarchy_rows_without_a_code_are_not_loaded() -> None:
    source = load_source(INDEX_FILE, UNIT_FILE)

    assert all(len(group.code) == 4 for group in source.unit_groups)
    assert "111" not in {group.code for group in source.unit_groups}


def test_a_missing_column_stops_the_load(tmp_path: Path) -> None:
    index = _workbook(
        tmp_path / "index.xlsx",
        INDEX_SHEET,
        ["UNIQUE ID", "SOC_2020", "INDEXOCC", "IND"],
        [["a1aa", 1111, "Manager", "Office"]],
    )
    unit = _workbook(tmp_path / "units.xlsx", UNIT_GROUP_SHEET, UNIT_HEADER, [_unit_row(1111)])

    with pytest.raises(ValueError, match="missing columns: ADD"):
        load_source(index, unit)


def test_a_code_that_is_not_four_digits_stops_the_load(tmp_path: Path) -> None:
    unit = _workbook(tmp_path / "units.xlsx", UNIT_GROUP_SHEET, UNIT_HEADER, [_unit_row("12A4")])
    index = _workbook(tmp_path / "index.xlsx", INDEX_SHEET, INDEX_HEADER, [])

    with pytest.raises(ValueError, match="not a four-digit SOC code"):
        load_source(index, unit)


def test_a_duplicate_unit_group_stops_the_load(tmp_path: Path) -> None:
    unit = _workbook(
        tmp_path / "units.xlsx",
        UNIT_GROUP_SHEET,
        UNIT_HEADER,
        [_unit_row(1111), _unit_row(1111, "Again")],
    )
    index = _workbook(tmp_path / "index.xlsx", INDEX_SHEET, INDEX_HEADER, [])

    with pytest.raises(ValueError, match="appears twice"):
        load_source(index, unit)


def test_a_duplicate_index_entry_stops_the_load(tmp_path: Path) -> None:
    unit = _workbook(tmp_path / "units.xlsx", UNIT_GROUP_SHEET, UNIT_HEADER, [_unit_row(1111)])
    index = _workbook(
        tmp_path / "index.xlsx",
        INDEX_SHEET,
        INDEX_HEADER,
        [["a1", 1111, "Manager", None, None], ["a2", 1111, "Manager", None, None]],
    )

    with pytest.raises(ValueError, match="duplicate entry"):
        load_source(index, unit)


def test_an_index_code_with_no_unit_group_stops_the_load(tmp_path: Path) -> None:
    unit = _workbook(tmp_path / "units.xlsx", UNIT_GROUP_SHEET, UNIT_HEADER, [_unit_row(1111)])
    index = _workbook(
        tmp_path / "index.xlsx",
        INDEX_SHEET,
        INDEX_HEADER,
        [["a1", 2222, "Engineer", None, None]],
    )

    with pytest.raises(ValueError, match="index codes with no unit group: 2222"):
        load_source(index, unit)


def test_the_ons_see_marker_is_counted_and_never_loaded(tmp_path: Path) -> None:
    unit = _workbook(tmp_path / "units.xlsx", UNIT_GROUP_SHEET, UNIT_HEADER, [_unit_row(1111)])
    index = _workbook(
        tmp_path / "index.xlsx",
        INDEX_SHEET,
        INDEX_HEADER,
        [["a1", "}}}}", "Advisor", None, None], ["a2", 1111, "Adviser", None, None]],
    )

    source = load_source(index, unit)

    assert source.cross_references == 1
    assert [entry.index_title for entry in source.index_entries] == ["Adviser"]


def test_a_file_that_does_not_match_its_sidecar_is_refused(tmp_path: Path) -> None:
    raw = tmp_path / "file.xlsx"
    raw.write_bytes(b"not the real file")
    sidecar = tmp_path / "file.json"
    sidecar.write_text(f'{{"sha256": "{sha256_of(raw)}"}}', encoding="utf-8")
    check_against_sidecar(raw, sidecar)

    raw.write_bytes(b"changed")

    with pytest.raises(ValueError, match=r"does not match file\.json"):
        check_against_sidecar(raw, sidecar)
