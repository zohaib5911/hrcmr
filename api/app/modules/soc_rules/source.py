"""Reads the GOV.UK Immigration Rules pages into rules-data rows (plan 6.10 and 8.17, T15.2).

Pure parsing: no database and no network. ``data/import_rules.py`` checks each saved page against
its sidecar SHA-256; ``importer.py`` writes what ``load_rules_source`` returns into a draft version.

Every figure comes from the page. Anything the parser does not recognise (a new column, a rate cell
in a new format, a missing table) stops it with a ValueError, so a changed page is read by a person
before it can reach a draft.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Any

from app.modules.soc_rules.models import NATIONS

if TYPE_CHECKING:
    from pathlib import Path

SKILLED_OCCUPATIONS = "skilled-occupations"
SALARY_LIST = "immigration-salary-list"
SKILLED_WORKER = "skilled-worker"
PAGE_KINDS = (SKILLED_OCCUPATIONS, SALARY_LIST, SKILLED_WORKER)
BASE_URL = "https://www.gov.uk/guidance/immigration-rules/immigration-rules-appendix-"
PAGE_URLS = {kind: BASE_URL + kind for kind in PAGE_KINDS}

RATE_TABLES = ("1", "1a", "2", "2aa", "2a", "2b")
PAY_SCALE_CODE_TABLES = ("3", "3a")
ALL_TABLES = (*RATE_TABLES, *PAY_SCALE_CODE_TABLES, "4", "5", "6")
# Which table's notes a table borrows ("the notes accompanying Table 1 also apply to this table").
NOTES_FROM = {"1a": "1", "2aa": "2", "2a": "2", "2b": "2"}

EN_DASH = "\u2013"  # GOV.UK separates a title from its condition with " \u2013 "
MONEY = r"£\s?([\d,]+(?:\.\d{1,2})?)"
CODE_TITLE = re.compile(r"^([1-9]\d{3})\s+(.+)$")
NATION_SUFFIX = re.compile(r"^(.*?)\s*\((England|Scotland|Wales|Northern Ireland)\)$")
RATE_CELL = re.compile(rf"^{MONEY}\s*\({MONEY} per hour\)$")
TABLE_HEADING = re.compile(r"^Table (\d+[a-z]*): ")
WEEK_HOURS = re.compile(r"based on an? (\d+(?:\.\d+)?)[- ]hour(?: working)? week")
LINE_HOURS = re.compile(r"\((?:based on an? )?(\d+(?:\.\d+)?)\s*-?\s*hour week\)")
FTE_HOURLY = re.compile(rf"\(FTE {MONEY} per hour\)")
SEE_TABLE = re.compile(r"See relevant pay (?:band|scale) in Table (\d)")
AS_CODE = re.compile(r"^As SOC 2020 occupation code (\d{4})$")


# ---------------------------------------------------------------------------------------------
# Rows


@dataclass(frozen=True)
class SourcePage:
    kind: str
    url: str
    file: str
    sha256: str
    bytes: int
    govuk_updated_at: str
    retrieved_on: str

    def as_json(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "url": self.url,
            "file": self.file,
            "sha256": self.sha256,
            "bytes": self.bytes,
            "govuk_updated_at": self.govuk_updated_at,
            "retrieved_on": self.retrieved_on,
        }


@dataclass(frozen=True)
class GoingRateRow:
    table: str
    soc_code: str
    title: str
    administration: str
    related_titles: tuple[str, ...]
    soc2010_codes: tuple[str, ...]
    annual_rate: Decimal | None
    hourly_rate: Decimal | None
    rate_90: Decimal | None
    rate_80: Decimal | None
    rate_70: Decimal | None
    phd_points_eligible: bool | None
    basis_hours: Decimal | None
    notes: str


@dataclass(frozen=True)
class PayScaleRow:
    source_table: str
    soc_code: str | None
    administration: str
    band_or_role: str
    annual_rate: Decimal
    basis_hours: Decimal | None


@dataclass(frozen=True)
class IneligibleRow:
    soc_code: str
    title: str
    related_titles: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class ShortageRow:
    list_name: str
    soc_code: str
    title: str
    condition_text: str
    job_types: tuple[str, ...]
    nations: tuple[str, ...]
    removal_date: dt.date


@dataclass(frozen=True)
class SalaryRuleRow:
    option: str
    general_threshold: Decimal
    going_rate_pct: int
    criteria_key: str
    applies_to: str
    requirement_text: str
    further_rules: str


@dataclass(frozen=True)
class RulesSource:
    pages: tuple[SourcePage, ...]
    going_rates: tuple[GoingRateRow, ...]
    pay_scales: tuple[PayScaleRow, ...]
    ineligible: tuple[IneligibleRow, ...]
    shortage: tuple[ShortageRow, ...]
    salary_rules: tuple[SalaryRuleRow, ...]
    table_notes: dict[str, str]

    @property
    def effective_from(self) -> dt.date:
        return max(dt.date.fromisoformat(p.govuk_updated_at[:10]) for p in self.pages)


# ---------------------------------------------------------------------------------------------
# A small reader for GOV.UK pages: headings, paragraphs, tables (cells as lines), list items


@dataclass
class Table:
    heading: str
    notes: list[str]
    rows: list[list[list[str]]]  # row -> cell -> lines (split at <br>)


@dataclass
class _Item:
    lines: list[str]
    children: list[_Item]


class _PageReader(HTMLParser):
    BLOCKS = frozenset({"p", "li", "h2", "h3", "h4"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[Table] = []
        self.paragraphs: list[str] = []  # every <p>/<li> text, in page order
        self.updated_at = ""
        self._heading = ""
        self._notes: list[str] = []
        self._text: list[str] | None = None
        self._text_tag = ""
        self._table: Table | None = None
        self._cell: list[str] | None = None
        self._in_main = False

    # text helpers
    def _flush_line(self, target: list[str], buffer: list[str]) -> None:
        line = " ".join("".join(buffer).split())
        if line:
            target.append(line)
        buffer.clear()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "meta" and values.get("name") == "govuk:updated-at":
            self.updated_at = values.get("content") or ""
        if tag == "main":
            self._in_main = True
        if not self._in_main:
            return
        if tag == "table":
            self._table = Table(self._heading, list(self._notes), [])
        elif tag == "tr" and self._table is not None:
            self._table.rows.append([])
        elif tag in ("td", "th") and self._table is not None:
            self._cell = []
            self._cell_buffer: list[str] = []
        elif tag == "br" and self._cell is not None:
            self._flush_line(self._cell, self._cell_buffer)
        elif tag in self.BLOCKS and self._table is None:
            if self._text is not None and self._text_tag == "li" and tag == "li":
                self._close_text()  # a nested list: the parent item's own text ends here
            self._text, self._text_tag = [], tag

    def _close_text(self) -> None:
        if self._text is None:
            return
        line = " ".join("".join(self._text).split())
        tag = self._text_tag
        self._text = None
        if not line:
            return
        if tag in ("h2", "h3", "h4"):
            self._heading, self._notes = line, []
        else:
            self._notes.append(line)
            self.paragraphs.append(line)

    def handle_endtag(self, tag: str) -> None:
        if tag == "main":
            self._in_main = False
        if tag in ("td", "th") and self._cell is not None and self._table is not None:
            self._flush_line(self._cell, self._cell_buffer)
            self._table.rows[-1].append(self._cell)
            self._cell = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None
        elif tag in self.BLOCKS and self._text is not None:
            self._close_text()

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell_buffer.append(data)
        elif self._text is not None:
            self._text.append(data)


def _read(html: str) -> _PageReader:
    reader = _PageReader()
    reader.feed(html)
    reader.close()
    return reader


# ---------------------------------------------------------------------------------------------
# Small parsers


def _money(text: str) -> Decimal:
    return Decimal(text.replace(",", ""))


def _cell(cell: list[str]) -> str:
    return " ".join(cell)


def _bullets(cell: list[str]) -> tuple[str, ...]:
    return tuple(line.lstrip("•").strip() for line in cell if line.lstrip("•").strip())


def _codes(cell: list[str]) -> tuple[str, ...]:
    return tuple(re.findall(r"\b\d{4}\b", _cell(cell)))


def _code_title(cell: list[str], where: str) -> tuple[str, str, str, str]:
    """``1111 Title (Nation)`` plus any "Note: ..." lines -> code, title, nation, note."""
    first, *rest = cell
    note = " ".join(rest)
    if " Note: " in first:
        first, extra = first.split(" Note: ", 1)
        note = f"Note: {extra} {note}".strip()
    match = CODE_TITLE.match(first)
    if not match:
        raise ValueError(f"{where}: no SOC 2020 code in {first!r}")
    code, title = match.groups()
    nation = ""
    suffix = NATION_SUFFIX.match(title)
    if suffix:
        title, nation = suffix.groups()
    return code, title.strip(), nation, note


def _rate_cell(text: str, where: str) -> tuple[Decimal | None, Decimal | None]:
    if text == "Not applicable":
        return None, None
    match = RATE_CELL.match(text)
    if not match:
        raise ValueError(f"{where}: unrecognised rate {text!r}")
    return _money(match.group(1)), _money(match.group(2))


def _yes_no(text: str, where: str) -> bool:
    if text not in ("Yes", "No"):
        raise ValueError(f"{where}: expected Yes or No, got {text!r}")
    return text == "Yes"


def _week_hours(text: str) -> Decimal | None:
    match = WEEK_HOURS.search(text)
    return Decimal(match.group(1)) if match else None


def _uk_date(text: str, where: str) -> dt.date:
    try:
        return dt.datetime.strptime(text.strip(), "%d %B %Y").replace(tzinfo=dt.UTC).date()
    except ValueError as exc:
        raise ValueError(f"{where}: unrecognised date {text!r}") from exc


# ---------------------------------------------------------------------------------------------
# Appendix Skilled Occupations


def _tables_by_number(reader: _PageReader) -> dict[str, Table]:
    found: dict[str, Table] = {}
    for table in reader.tables:
        match = TABLE_HEADING.match(table.heading)
        if match:
            if match.group(1) in found:
                raise ValueError(f"Table {match.group(1)} appears twice")
            found[match.group(1)] = table
    missing = [n for n in ALL_TABLES if n not in found]
    if missing:
        raise ValueError(f"Appendix Skilled Occupations: tables missing: {', '.join(missing)}")
    return found


_RATE_COLUMNS = {
    "SOC 2020 occupation code": "code",
    "Equivalent SOC 2010 occupation code(s)": "soc2010",
    "Examples of related job titles (non-exclusive)": "related",
    "Eligible for PhD points (SW)?": "phd",
}


def _rate_column(header: str, where: str) -> str:
    if header in _RATE_COLUMNS:
        return _RATE_COLUMNS[header]
    for prefix, key in (
        ("Going rate", "annual"),
        ("90% of going rate", "rate_90"),
        ("80% of going rate", "rate_80"),
        ("70% of going rate", "rate_70"),
    ):
        if header.startswith(prefix):
            return key
    raise ValueError(f"{where}: unknown column {header!r}")


def _rate_table(number: str, table: Table, hours: Decimal) -> list[GoingRateRow]:
    where = f"Table {number}"
    header, *rows = table.rows
    columns = [_rate_column(_cell(c), where) for c in header]
    if columns[0] != "code" or "annual" not in columns:
        raise ValueError(f"{where}: unexpected header {columns}")
    out: list[GoingRateRow] = []
    for row in rows:
        values = dict(zip(columns, row, strict=True))
        code, title, nation, note = _code_title(values["code"], where)
        annual, hourly = _rate_cell(_cell(values["annual"]), f"{where} {code}")
        reduced = {
            key: _rate_cell(_cell(values[key]), f"{where} {code}")[0]
            for key in ("rate_90", "rate_80", "rate_70")
            if key in values
        }
        out.append(
            GoingRateRow(
                table=number,
                soc_code=code,
                title=title,
                administration=nation,
                related_titles=_bullets(values.get("related", [])),
                soc2010_codes=_codes(values.get("soc2010", [])),
                annual_rate=annual,
                hourly_rate=hourly,
                rate_90=reduced.get("rate_90"),
                rate_80=reduced.get("rate_80"),
                rate_70=reduced.get("rate_70"),
                phd_points_eligible=(
                    _yes_no(_cell(values["phd"]), f"{where} {code}") if "phd" in values else None
                ),
                basis_hours=hours,
                notes=note,
            )
        )
    return out


def _context_nation(line: str) -> str:
    for nation in NATIONS:
        if nation in line:
            return nation
    if "Scottish" in line:
        return "Scotland"
    if "Welsh" in line:
        return "Wales"
    return ""


def _pay_cell(
    number: str, code: str, nation: str, cell: list[str]
) -> tuple[list[PayScaleRow], Decimal | None, Decimal | None, Decimal | None, str]:
    """A Table 3/3a "Going rate (annual)" cell -> pay rows, or one plain rate, plus notes.

    Returns (rows, single annual rate, its FTE hourly rate, default weekly hours, note)."""
    where = f"Table {number} {code}"
    text = _cell(cell)
    # The closing sentence ("These going rates are per year and based on a 40-hour working week")
    # sets the default; a bullet's own "(35-hour week)" overrides it.
    closing = text.find("These going rates")
    default_hours = _week_hours(text[closing:]) if closing >= 0 else None
    see = SEE_TABLE.search(text)
    note = f"See Table {see.group(1)}" if see else ""
    # A cell that is one amount and nothing else ("£23,656 (FTE £12.26 per hour)").
    single = re.fullmatch(rf"{MONEY}(?: p\.a\.)?\s*(?:\(FTE {MONEY} per hour\))?", text)
    if single:
        fte = single.group(2)
        return [], _money(single.group(1)), _money(fte) if fte else None, None, note
    rows: list[PayScaleRow] = []
    label = ""
    context_nation = nation
    for raw in cell:
        line = raw.lstrip("•").strip()
        amount = re.search(MONEY, line)
        if not amount:
            # A heading line ("Other medical professionals:", "Classroom Assistant SEN:").
            label = line.rstrip(":").strip()
            context_nation = nation or _context_nation(line) or context_nation
            continue
        before = line[: amount.start()].strip().rstrip(":").strip()
        role = before or label
        if not role:
            raise ValueError(f"{where}: an amount with no role in {line!r}")
        hours_match = LINE_HOURS.search(line)
        hours = Decimal(hours_match.group(1)) if hours_match else default_hours
        rows.append(
            PayScaleRow(
                source_table=number,
                soc_code=code,
                administration=context_nation,
                band_or_role=role,
                annual_rate=_money(amount.group(1)),
                basis_hours=hours,
            )
        )
    if not rows and not see:
        raise ValueError(f"{where}: no rates and no table reference in {text!r}")
    return rows, None, None, default_hours, note


def _pay_scale_code_table(
    number: str, table: Table
) -> tuple[list[GoingRateRow], list[PayScaleRow]]:
    where = f"Table {number}"
    header, *rows = table.rows
    names = [_cell(c) for c in header]
    expected = [
        "SOC 2020 occupation code",
        "Equivalent SOC 2010 occupation code(s)",
        "Examples of related job titles (non-exclusive)",
        "Going rate (annual)",
        "National pay scale source",
    ]
    if names != expected:
        raise ValueError(f"{where}: unexpected header {names}")
    going: list[GoingRateRow] = []
    pay: list[PayScaleRow] = []
    by_code: dict[str, list[tuple[str, list[PayScaleRow]]]] = {}
    for code_cell, soc2010, related, rate, source in rows:
        code, title, nation, note = _code_title(code_cell, where)
        rate_text = _cell(rate)
        alias = AS_CODE.match(rate_text)
        if alias:
            # "As SOC 2020 occupation code 2211": the same rows, nation by nation.
            copied = by_code.get(alias.group(1))
            if not copied:
                raise ValueError(f"{where} {code}: refers to {alias.group(1)}, not read yet")
            for copied_nation, copied_rows in copied:
                going.append(
                    GoingRateRow(
                        table=number,
                        soc_code=code,
                        title=title,
                        administration=copied_nation,
                        related_titles=_bullets(related),
                        soc2010_codes=_codes(soc2010),
                        annual_rate=None,
                        hourly_rate=None,
                        rate_90=None,
                        rate_80=None,
                        rate_70=None,
                        phd_points_eligible=None,
                        basis_hours=None,
                        notes=" ".join(p for p in (note, rate_text) if p),
                    )
                )
                pay.extend(
                    PayScaleRow(
                        source_table=r.source_table,
                        soc_code=code,
                        administration=r.administration,
                        band_or_role=r.band_or_role,
                        annual_rate=r.annual_rate,
                        basis_hours=r.basis_hours,
                    )
                    for r in copied_rows
                )
            continue
        rows_here, annual, hourly, hours, see_note = _pay_cell(number, code, nation, rate)
        by_code.setdefault(code, []).append((nation, rows_here))
        pay.extend(rows_here)
        going.append(
            GoingRateRow(
                table=number,
                soc_code=code,
                title=title,
                administration=nation,
                related_titles=_bullets(related),
                soc2010_codes=_codes(soc2010),
                annual_rate=annual,
                hourly_rate=hourly,
                rate_90=None,
                rate_80=None,
                rate_70=None,
                phd_points_eligible=None,
                basis_hours=hours,
                notes=" ".join(p for p in (note, see_note, f"Source: {_cell(source)}") if p),
            )
        )
    return going, pay


def _band_table(number: str, table: Table, hours: dict[str, Decimal | None]) -> list[PayScaleRow]:
    """Table 4 (bands) or Table 5 (teacher roles): one column per administration."""
    where = f"Table {number}"
    header, *rows = table.rows
    administrations = [_cell(c) for c in header[1:]]
    out: list[PayScaleRow] = []
    for row in rows:
        label = _cell(row[0])
        for administration, value in zip(administrations, row[1:], strict=True):
            text = _cell(value)
            if text in ("-", EN_DASH, ""):
                continue
            match = re.fullmatch(MONEY, text)
            if not match:
                raise ValueError(f"{where} {label}: unrecognised rate {text!r}")
            out.append(
                PayScaleRow(
                    source_table=number,
                    soc_code=None,
                    administration=administration,
                    band_or_role=label,
                    annual_rate=_money(match.group(1)),
                    basis_hours=hours.get(administration, hours.get("")),
                )
            )
    return out


def _table4_hours(notes: str) -> dict[str, Decimal | None]:
    match = re.search(
        r"based on an? (\d+(?:\.\d+)?)-hour week \(in Scotland, an? (\d+(?:\.\d+)?)-hour week\)",
        notes,
    )
    if not match:
        raise ValueError("Table 4: the weekly hours note has changed")
    return {"": Decimal(match.group(1)), "Scotland": Decimal(match.group(2))}


def _ineligible_table(table: Table) -> list[IneligibleRow]:
    header, *rows = table.rows
    if _cell(header[0]) != "SOC 2020 occupation code":
        raise ValueError(f"Table 6: unexpected header {header}")
    reason = TABLE_HEADING.sub("", table.heading)
    out: list[IneligibleRow] = []
    for row in rows:
        code, title, _, note = _code_title(row[0], "Table 6")
        out.append(
            IneligibleRow(
                soc_code=code,
                title=title,
                related_titles=_bullets(row[1]) if len(row) > 1 else (),
                reason=" ".join(p for p in (reason, note) if p),
            )
        )
    return out


def parse_skilled_occupations(
    html: str,
) -> tuple[list[GoingRateRow], list[PayScaleRow], list[IneligibleRow], dict[str, str]]:
    tables = _tables_by_number(_read(html))
    notes = {number: " ".join(tables[number].notes) for number in ALL_TABLES}
    going: list[GoingRateRow] = []
    pay: list[PayScaleRow] = []
    for number in RATE_TABLES:
        hours = _week_hours(notes[number]) or _week_hours(notes.get(NOTES_FROM.get(number, ""), ""))
        if hours is None:
            raise ValueError(f"Table {number}: no weekly hours in its notes")
        going.extend(_rate_table(number, tables[number], hours))
    for number in PAY_SCALE_CODE_TABLES:
        rows, rates = _pay_scale_code_table(number, tables[number])
        going.extend(rows)
        pay.extend(rates)
    pay.extend(_band_table("4", tables["4"], _table4_hours(notes["4"])))
    # Table 5: "based on the definition of a full-time teacher", so no weekly hours to store.
    pay.extend(_band_table("5", tables["5"], {"": _week_hours(notes["5"])}))
    ineligible = _ineligible_table(tables["6"])
    _check_unique([(r.table, r.soc_code, r.administration) for r in going], "going rate rows")
    _check_unique([(r.soc_code,) for r in ineligible], "Table 6 codes")
    return going, pay, ineligible, notes


def _check_unique(keys: list[tuple[str, ...]], what: str) -> None:
    seen: set[tuple[str, ...]] = set()
    for key in keys:
        if key in seen:
            raise ValueError(f"duplicate {what}: {key}")
        seen.add(key)


# ---------------------------------------------------------------------------------------------
# Appendix Immigration Salary List


def parse_salary_list(html: str) -> list[ShortageRow]:
    reader = _read(html)
    tables = [t for t in reader.tables if t.rows and _cell(t.rows[0][0]).startswith("SOC 2020")]
    if len(tables) != 1:
        raise ValueError(f"Immigration Salary List: expected one table, found {len(tables)}")
    first, second, *rows = tables[0].rows
    nations = [_cell(c) for c in second[1:5]]
    if nations != list(NATIONS) or _cell(first[-1]) != "Removal date":
        raise ValueError("Immigration Salary List: unexpected header")
    out: list[ShortageRow] = []
    for row in rows:
        code, rest, _, note = _code_title(row[0], "ISL")
        title, _, condition = rest.partition(f" {EN_DASH} ")
        flags = [_cell(c) for c in row[1:5]]
        if any(f not in ("Yes", "-", EN_DASH) for f in flags):
            raise ValueError(f"ISL {code}: unexpected nation flags {flags}")
        out.append(
            ShortageRow(
                list_name="ISL",
                soc_code=code,
                title=title.strip(),
                condition_text=" ".join(p for p in (condition.strip(), note) if p),
                job_types=(),
                nations=tuple(n for n, f in zip(NATIONS, flags, strict=True) if f == "Yes"),
                removal_date=_uk_date(_cell(row[5]), f"ISL {code}"),
            )
        )
    _check_unique([(r.soc_code,) for r in out], "ISL codes")
    return out


# ---------------------------------------------------------------------------------------------
# Appendix Skilled Worker: the Temporary Shortage List (SW 6.1A) and the points options (SW 4.2)


class _ListAfterMarker(HTMLParser):
    """Collects the first <ul> after a <strong>marker</strong>, with nested lists as children."""

    def __init__(self, marker: str) -> None:
        super().__init__(convert_charrefs=True)
        self.marker = marker
        self.items: list[_Item] = []
        self._strong: list[str] | None = None
        self._armed = False
        self._done = False
        self._stack: list[list[_Item]] = []
        self._current: list[_Item] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._done:
            return
        if tag == "strong":
            self._strong = []
        elif tag == "ul" and self._armed:
            if not self._stack:
                self._stack.append(self.items)
            else:
                self._stack.append(self._current[-1].children)
        elif tag == "li" and self._stack:
            item = _Item([], [])
            self._stack[-1].append(item)
            self._current.append(item)

    def handle_endtag(self, tag: str) -> None:
        if self._done:
            return
        if tag == "strong" and self._strong is not None:
            if " ".join("".join(self._strong).split()) == self.marker:
                self._armed = True
            self._strong = None
        elif tag == "li" and self._current:
            self._current.pop()
        elif tag == "ul" and self._stack:
            self._stack.pop()
            if not self._stack:
                self._done = True

    def handle_data(self, data: str) -> None:
        if self._strong is not None:
            self._strong.append(data)
        elif self._current and not self._done:
            self._current[-1].lines.append(data)


def _item_text(item: _Item) -> str:
    return " ".join("".join(item.lines).split())


def parse_temporary_shortage_list(html: str) -> list[ShortageRow]:
    reader = _read(html)
    rule = next((p for p in reader.paragraphs if p.startswith("SW 6.1A.")), None)
    if rule is None:
        raise ValueError("Appendix Skilled Worker: SW 6.1A not found")
    expiry = next(
        (
            re.search(r"before (\d{1,2} \w+ \d{4})", p)
            for p in reader.paragraphs
            if "certificate of sponsorship issued by a sponsor to an applicant before" in p
        ),
        None,
    )
    if expiry is None:
        raise ValueError("Appendix Skilled Worker: the SW 6.1A(b) end date was not found")
    removal = _uk_date(expiry.group(1), "SW 6.1A(b)")
    lister = _ListAfterMarker("Temporary Shortage List")
    lister.feed(html)
    if not lister.items:
        raise ValueError("Appendix Skilled Worker: the Temporary Shortage List was not found")
    out: list[ShortageRow] = []
    for item in lister.items:
        code, rest, _, _ = _code_title([_item_text(item)], "TSL")
        title, _, condition = rest.partition(f" {EN_DASH} ")
        job_types = tuple(_item_text(child) for child in item.children)
        if job_types and not condition:
            raise ValueError(f"TSL {code}: job types listed with no condition")
        out.append(
            ShortageRow(
                list_name="TSL",
                soc_code=code,
                title=title.strip(),
                condition_text=condition.strip() or "all jobs",
                job_types=job_types,
                nations=NATIONS,
                removal_date=removal,
            )
        )
    _check_unique([(r.soc_code,) for r in out], "TSL codes")
    return out


_CRITERIA = (
    ("PhD in a STEM subject", "stem_phd"),
    ("PhD in a subject relevant", "phd"),
    ("Immigration Salary List", "isl"),
    ("new entrant", "new_entrant"),
    ("listed health or education occupation", "health_education"),
    ("The applicant\u2019s salary equals or exceeds both", "standard"),
)


def _applies_to(option: str, paragraphs: list[str]) -> str:
    """SW 4.2: A to E for everyone, F to J only under SW 4.2(b) (before 4 April 2024, or a Health
    and Care ASHE salary job), K only for a Table 3/3a job. The wording is checked, not assumed."""
    text = " ".join(paragraphs)
    if option == "K":
        if "can only be awarded points from option K if" not in text:
            raise ValueError("SW 4.2(c) wording changed")
        return "health_care"
    if option in "FGHIJ":
        if "can only be awarded points from options F to J if" not in text or (
            "before 4 April 2024" not in text
        ):
            raise ValueError("SW 4.2(b) wording changed")
        return "transitional_pre_2024"
    if "can only be awarded points from options A to E" not in text:
        raise ValueError("SW 4.2(a) wording changed")
    return "new"


def parse_salary_rules(html: str) -> list[SalaryRuleRow]:
    reader = _read(html)
    tables = [
        t for t in reader.tables if [_cell(c) for c in t.rows[0]][:2] == ["Option", "Requirements"]
    ]
    if len(tables) != 1:
        raise ValueError(
            f"Appendix Skilled Worker: expected one points-options table, got {len(tables)}"
        )
    out: list[SalaryRuleRow] = []
    for row in tables[0].rows[1:]:
        option, requirement, further, _points = (_cell(c) for c in row)
        threshold = re.search(rf"{MONEY} per year", requirement)
        if not threshold:
            raise ValueError(f"option {option}: no general threshold in {requirement!r}")
        pct_match = re.search(r"(\d+)% of the going rate", requirement)
        if pct_match:
            pct = int(pct_match.group(1))
        elif "the going rate for the SOC 2020 occupation code" in requirement:
            pct = 100
        else:
            raise ValueError(f"option {option}: no going-rate share in {requirement!r}")
        key = next((k for phrase, k in _CRITERIA if phrase in requirement), None)
        if key is None:
            raise ValueError(f"option {option}: unrecognised criteria in {requirement!r}")
        out.append(
            SalaryRuleRow(
                option=option,
                general_threshold=_money(threshold.group(1)),
                going_rate_pct=pct,
                criteria_key=key,
                applies_to=_applies_to(option, reader.paragraphs),
                requirement_text=requirement,
                further_rules=further,
            )
        )
    if [r.option for r in out] != list("ABCDEFGHIJK"):
        raise ValueError(f"points options: expected A to K, got {[r.option for r in out]}")
    return out


# ---------------------------------------------------------------------------------------------
# Files


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_page(path: Path, sidecar: Path, kind: str) -> tuple[str, SourcePage]:
    """The page's HTML and its provenance. A hash that differs from the sidecar stops the load."""
    record = json.loads(sidecar.read_text(encoding="utf-8"))
    actual = sha256_of(path)
    if actual != record["sha256"]:
        raise ValueError(f"{path.name}: SHA-256 {actual} does not match its sidecar")
    html = path.read_text(encoding="utf-8")
    updated = _read(html).updated_at
    if updated != record["govuk_updated_at"]:
        raise ValueError(f"{path.name}: GOV.UK updated stamp {updated!r} differs from sidecar")
    return html, SourcePage(
        kind=kind,
        url=str(record["source_url"]),
        file=str(record["file"]),
        sha256=actual,
        bytes=int(record["bytes"]),
        govuk_updated_at=updated,
        retrieved_on=str(record["retrieved_on"]),
    )


def load_rules_source(pages: dict[str, tuple[Path, Path]]) -> RulesSource:
    """``pages`` maps each kind in PAGE_KINDS to (html file, sidecar json)."""
    if sorted(pages) != sorted(PAGE_KINDS):
        raise ValueError(f"expected pages {PAGE_KINDS}, got {sorted(pages)}")
    return rules_source_from_read(
        {kind: read_page(html, sidecar, kind) for kind, (html, sidecar) in pages.items()}
    )


def page_from_bytes(kind: str, url: str, data: bytes, retrieved_on: str) -> tuple[str, SourcePage]:
    """A page fetched now: its HTML and its provenance, with the SHA-256 of the bytes as fetched."""
    html = data.decode("utf-8")
    return html, SourcePage(
        kind=kind,
        url=url,
        file="",
        sha256=hashlib.sha256(data).hexdigest(),
        bytes=len(data),
        govuk_updated_at=_read(html).updated_at,
        retrieved_on=retrieved_on,
    )


def rules_source_from_read(read: dict[str, tuple[str, SourcePage]]) -> RulesSource:
    """The parsed rules from pages already read (their HTML and provenance), one per kind."""
    if sorted(read) != sorted(PAGE_KINDS):
        raise ValueError(f"expected pages {PAGE_KINDS}, got {sorted(read)}")
    going, pay, ineligible, notes = parse_skilled_occupations(read[SKILLED_OCCUPATIONS][0])
    shortage = [
        *parse_salary_list(read[SALARY_LIST][0]),
        *parse_temporary_shortage_list(read[SKILLED_WORKER][0]),
    ]
    return RulesSource(
        pages=tuple(read[kind][1] for kind in PAGE_KINDS),
        going_rates=tuple(going),
        pay_scales=tuple(pay),
        ineligible=tuple(ineligible),
        shortage=tuple(shortage),
        salary_rules=tuple(parse_salary_rules(read[SKILLED_WORKER][0])),
        table_notes=notes,
    )
