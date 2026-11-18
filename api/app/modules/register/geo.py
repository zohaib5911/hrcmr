"""Town -> ITL1 region from the ONS Index of Place Names bulk file, plus the optional
Companies House (Free Company Data Product) match. Pure functions: no network, and the
caller supplies the downloaded bytes."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import re
from typing import IO, TYPE_CHECKING, NamedTuple, cast

from sqlalchemy import select

from app.core.logging import get_logger
from app.modules.register.ingest import normalise
from app.modules.register.models import CompanyDataset, CompanyMatch, PlaceDataset, Sponsor

if TYPE_CHECKING:
    import uuid
    from collections.abc import Iterable, Iterator

    from sqlalchemy.ext.asyncio import AsyncSession

ITL1_REGIONS = (
    "North East",
    "North West",
    "Yorkshire and The Humber",
    "East Midlands",
    "West Midlands",
    "East of England",
    "London",
    "South East",
    "South West",
    "Wales",
    "Scotland",
    "Northern Ireland",
)
_BY_KEY = {normalise(r): r for r in ITL1_REGIONS}
_BY_KEY["yorkshire and the humber"] = "Yorkshire and The Humber"
_BY_KEY["yorkshire humber"] = "Yorkshire and The Humber"
_BY_KEY["east"] = "East of England"
PLACE_HEADERS = ("place_name", "county", "region", "lat", "lon")
# ONS region/country codes (GSS). The Index of Place Names gives Welsh and Scottish places a
# W99999999/S99999999 region, so country codes fill in for the devolved nations.
_REGION_CODES = {
    "E12000001": "North East",
    "E12000002": "North West",
    "E12000003": "Yorkshire and The Humber",
    "E12000004": "East Midlands",
    "E12000005": "West Midlands",
    "E12000006": "East of England",
    "E12000007": "London",
    "E12000008": "South East",
    "E12000009": "South West",
}
# European Electoral Region codes (eer<yy>cd) cover the same nine English regions, in the
# same order. In IPN_GB_2024.csv the rgn23cd column is blank on about 43,000 rows and says
# "North East" on about 14,000 rows that are elsewhere (Bristol's locality row among them),
# while eer23cd is filled and right, so the EER code is read first.
_EER_CODES = {f"E1500000{i}": name for i, name in enumerate(_REGION_CODES.values(), start=1)}
_NATION_PREFIX = {"W": "Wales", "S": "Scotland", "N": "Northern Ireland"}
logger = get_logger("app.register.geo")

# SIC 2007 division (first two digits) -> section letter.
_SECTIONS = (
    ("A", 1, 3),
    ("B", 5, 9),
    ("C", 10, 33),
    ("D", 35, 35),
    ("E", 36, 39),
    ("F", 41, 43),
    ("G", 45, 47),
    ("H", 49, 53),
    ("I", 55, 56),
    ("J", 58, 63),
    ("K", 64, 66),
    ("L", 68, 68),
    ("M", 69, 75),
    ("N", 77, 82),
    ("O", 84, 84),
    ("P", 85, 85),
    ("Q", 86, 88),
    ("R", 90, 93),
    ("S", 94, 96),
    ("T", 97, 98),
    ("U", 99, 99),
)


class Place(NamedTuple):
    region: str
    lat: float | None
    lon: float | None


def region_name(value: str) -> str | None:
    return _BY_KEY.get(normalise(value))


def parse_places(content: bytes) -> dict[tuple[str, str], Place]:
    """Keyed by (normalised place, normalised county); ("place", "") is the place-only entry,
    set only when every row for that place names the same region."""
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    if tuple(reader.fieldnames or ()) != PLACE_HEADERS:
        raise ValueError("Unexpected place-name CSV columns")
    exact: dict[tuple[str, str], Place] = {}
    seen: dict[str, set[str]] = {}
    first: dict[str, Place] = {}
    for row in reader:
        region = region_name(row["region"] or "")
        name = normalise(row["place_name"] or "")
        if region is None or not name:
            continue
        try:
            place = Place(region, float(row["lat"]), float(row["lon"]))
        except (TypeError, ValueError):
            place = Place(region, None, None)
        exact.setdefault((name, normalise(row["county"] or "")), place)
        seen.setdefault(name, set()).add(region)
        first.setdefault(name, place)
    if not exact:
        raise ValueError("Empty place-name file refused")
    for name, regions in seen.items():
        if len(regions) == 1:
            exact[(name, "")] = first[name]
        else:  # a row with an empty county must not stand in for a name used in two regions
            exact.pop((name, ""), None)
    return exact


def _ons_region(row: dict[str, str], code_cols: list[str], name_cols: list[str]) -> str | None:
    for col in code_cols:
        code = row.get(col, "").strip().upper()
        if code in _EER_CODES:
            return _EER_CODES[code]
        if code in _REGION_CODES:
            return _REGION_CODES[code]
        if code[:1] in _NATION_PREFIX:
            return _NATION_PREFIX[code[:1]]
    for col in name_cols:
        if found := region_name(row.get(col, "")):
            return found
    return None


def normalise_places(content: bytes) -> bytes:
    """Accept the ONS Index of Place Names CSV (columns such as place22nm, cty22nm, ctyhistnm,
    ctyltnm, rgn22cd, ctry22cd, lat, long; the year digits vary by edition) or a file already
    in PLACE_HEADERS form, and return the five-column CSV ``parse_places`` reads. One row per
    county spelling, so a sponsor's county can match the current, historic or ceremonial name,
    or the region itself."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        # The ONS publishes the Index of Place Names in Windows-1252 (Gaelic and Welsh names
        # such as "A' Chrìon Làraich" in IPN_GB_2024.csv are not UTF-8 bytes).
        text = content.decode("cp1252")
    reader = csv.DictReader(io.StringIO(text))
    raw = [h or "" for h in reader.fieldnames or ()]
    if tuple(raw) == PLACE_HEADERS:
        parse_places(content)
        return content
    headers = {h.strip().lower(): h for h in raw}

    def cols(pattern: str) -> list[str]:
        return [headers[h] for h in sorted(headers) if re.fullmatch(pattern, h)]

    names = cols(r"place\d{2}nm")
    counties = cols(r"cty\d{2}nm|ctyhistnm|ctyltnm")
    region_codes = cols(r"eer\d{2}cd") + cols(r"rgn\d{2}cd") + cols(r"ctry\d{2}cd")
    region_names = cols(r"rgn\d{2}nm") + cols(r"ctry\d{2}nm")
    lat, lon = headers.get("lat"), headers.get("long")
    if not names or not (region_codes or region_names) or lat is None or lon is None:
        raise ValueError("Unexpected place-name CSV columns")
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(PLACE_HEADERS)
    seen: set[tuple[str, str, str]] = set()
    for row in reader:
        values = {k: v or "" for k, v in row.items() if k is not None}
        name = values[names[0]].strip()
        region = _ons_region(values, region_codes, region_names)
        if not name or region is None:
            continue
        # A sponsor's "county" is often its region ("London", "Greater London"): the region's own
        # name counts as one more county spelling, so such a town is placed exactly, not guessed.
        aliases = {region} | ({"Greater London"} if region == "London" else set())
        for county in ({values[c].strip() for c in counties} or {""}) | aliases:
            key = (normalise(name), normalise(county), region)
            if key in seen:
                continue
            seen.add(key)
            writer.writerow((name, county, region, values[lat].strip(), values[lon].strip()))
    result = out.getvalue().encode("utf-8")
    parse_places(result)  # refuses an empty or unusable file
    return result


def geocode(
    places: dict[tuple[str, str], Place], town: str, county: str
) -> tuple[Place | None, str]:
    """Precision: "exact" (town + county), "town" (town only, unambiguous), "none"."""
    t, c = normalise(town), normalise(county)
    if t and c and (t, c) in places:
        return places[(t, c)], "exact"
    if t and (t, "") in places:
        return places[(t, "")], "town"
    return None, "none"


def sic_section(code: str) -> str | None:
    digits = "".join(ch for ch in code.split("-")[0].strip() if ch.isdigit())
    if len(digits) < 2:
        return None
    division = int(digits[:2])
    return next((s for s, lo, hi in _SECTIONS if lo <= division <= hi), None)


_CH_COLUMNS = ("CompanyName", "CompanyNumber", "SICCode.SicText_1")
_INDEX_HEADER = ["name", "number", "section"]


def _company_rows(
    stream: IO[bytes], *, stored: bool = False
) -> Iterator[tuple[str, str, str | None]]:
    """Stream (normalised name, number, SIC section) rows from a Companies House CSV, or
    from a stored reduced index when ``stored``. Never holds the whole file in memory."""
    text = io.TextIOWrapper(stream, encoding="utf-8-sig", newline="")
    try:
        reader = csv.reader(text)
        header = [h.strip() for h in next(reader, [])]
        if stored and header == _INDEX_HEADER:
            for name, number, section in reader:
                yield name, number, section or None
            return
        if not set(_CH_COLUMNS) <= set(header):
            raise ValueError("Unexpected Companies House CSV columns")
        cols = [header.index(c) for c in _CH_COLUMNS]
        width = max(cols) + 1
        for row in reader:
            row += [""] * (width - len(row))
            key = normalise(row[cols[0]])
            if key:
                yield key, row[cols[1]].strip(), sic_section(row[cols[2]])
    finally:
        text.detach()  # the caller owns the stream


def _unambiguous(
    rows: Iterable[tuple[str, str, str | None]], wanted: set[str] | None = None
) -> dict[str, tuple[str, str | None]]:
    """Names that occur twice are dropped: a bulk match must never guess between two
    companies. With ``wanted``, only those names are kept (every occurrence still counts)."""
    found: dict[str, tuple[str, str | None]] = {}
    clash: set[str] = set()
    for key, number, section in rows:
        if wanted is not None and key not in wanted:
            continue
        if key in found:
            clash.add(key)
        found[key] = (number, section)
    return {k: v for k, v in found.items() if k not in clash}


def parse_companies(content: bytes) -> dict[str, tuple[str, str | None]]:
    """normalised company name -> (number, SIC section), unambiguous names only."""
    return _unambiguous(_company_rows(io.BytesIO(content)))


class _Hashing(io.RawIOBase):
    def __init__(self, raw: IO[bytes]) -> None:
        self.raw, self.digest = raw, hashlib.sha256()

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: memoryview) -> int:  # type: ignore[override]
        data = self.raw.read(len(buffer))
        buffer[: len(data)] = data
        self.digest.update(data)
        return len(data)


class CompanyIndex(NamedTuple):
    content: bytes  # gzip CSV: normalised name, number, SIC section; one line per source row
    sha256: str  # of the original file, exactly as supplied
    rows: int
    companies: dict[str, tuple[str, str | None]]  # unambiguous matches among ``wanted``


def build_company_index(source: bytes | IO[bytes], wanted: set[str]) -> CompanyIndex:
    """Stream a monthly bulk CSV (plain or gzip) into the reduced index that is stored.
    Every named row is kept (only three short fields), so whole-file duplicate rejection
    still works when a sponsor first appears in a later register import."""
    raw = io.BytesIO(source) if isinstance(source, bytes) else source
    hashing = _Hashing(raw)
    buffered = io.BufferedReader(hashing, buffer_size=1 << 20)
    gz_magic = buffered.peek(2)[:2] == b"\x1f\x8b"
    csv_stream = cast("IO[bytes]", gzip.GzipFile(fileobj=buffered) if gz_magic else buffered)
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", mtime=0) as packed:
        text = io.TextIOWrapper(packed, encoding="utf-8", newline="")
        writer = csv.writer(text)
        writer.writerow(_INDEX_HEADER)
        kept: list[tuple[str, str, str | None]] = []
        rows = 0
        for key, number, section in _company_rows(csv_stream):
            writer.writerow((key, number, section or ""))
            rows += 1
            if key in wanted:
                kept.append((key, number, section))
        text.flush()
        text.detach()
    while buffered.read(1 << 20):  # hash any bytes the CSV reader did not need
        pass
    return CompanyIndex(out.getvalue(), hashing.digest.hexdigest(), rows, _unambiguous(kept))


def parse_company_index(content: bytes, wanted: set[str]) -> dict[str, tuple[str, str | None]]:
    """Unambiguous matches for ``wanted`` from a stored dataset, streamed from the gzip."""
    with gzip.GzipFile(fileobj=io.BytesIO(content)) as stream:
        return _unambiguous(_company_rows(cast("IO[bytes]", stream), stored=True), wanted)


async def _sponsor_names(db: AsyncSession) -> set[str]:
    return set((await db.scalars(select(Sponsor.normalised_name))).all())


async def apply_geocoding(
    db: AsyncSession, places: dict[tuple[str, str], Place], *, only_missing: bool = True
) -> int:
    changed = 0
    for sponsor in (await db.scalars(select(Sponsor))).all():
        if only_missing and sponsor.place_precision != "none":
            continue
        place, precision = geocode(places, sponsor.town, sponsor.county)
        if place is None:
            continue
        sponsor.region_itl1, sponsor.lat, sponsor.lon = place.region, place.lat, place.lon
        sponsor.place_precision = precision
        changed += 1
    await db.flush()
    return changed


async def apply_companies_match(
    db: AsyncSession,
    companies: dict[str, tuple[str, str | None]],
    *,
    enabled: bool,
    dataset_id: uuid.UUID | None = None,
    refresh: bool = False,
) -> int:
    """Behind a flag: does nothing unless enabled. Exact normalised-name matches only."""
    if not enabled:
        return 0
    changed = 0
    provenance = {m.sponsor_id: m for m in (await db.scalars(select(CompanyMatch))).all()}
    for sponsor in (await db.scalars(select(Sponsor))).all():
        previous = provenance.get(sponsor.id)
        if previous is not None and (refresh or previous.dataset_id != dataset_id):
            sponsor.companies_house_number = sponsor.sic_section = None
        if sponsor.companies_house_number:
            continue
        hit = companies.get(sponsor.normalised_name)
        if hit:
            sponsor.companies_house_number, sponsor.sic_section = hit
            if dataset_id is not None:
                if previous is None:
                    db.add(CompanyMatch(sponsor_id=sponsor.id, dataset_id=dataset_id))
                else:
                    previous.dataset_id = dataset_id
            changed += 1
        elif previous is not None:
            await db.delete(previous)
    await db.flush()
    return changed


async def load_place_dataset(
    db: AsyncSession, content: bytes, *, version: str, source: str
) -> tuple[PlaceDataset, int]:
    """Store a new place-name dataset as the active one and place every sponsor it can.
    Caller owns commit/rollback."""
    normalised = normalise_places(content)
    places = parse_places(normalised)
    dataset = PlaceDataset(
        version=version,
        source=source,
        sha256=hashlib.sha256(content).hexdigest(),
        row_count=normalised.count(b"\n") - 1,
        content=normalised,
    )
    db.add(dataset)
    await db.flush()
    return dataset, await apply_geocoding(db, places, only_missing=False)


async def geocode_from_latest_dataset(db: AsyncSession) -> int | None:
    """Called after every register import: place sponsors still unplaced. Returns None (and
    logs) when no dataset was ever loaded, so the import still succeeds but stays unplaced."""
    dataset = await db.scalar(
        select(PlaceDataset)
        .order_by(PlaceDataset.loaded_at.desc(), PlaceDataset.id.desc())
        .limit(1)
    )
    if dataset is None:
        logger.warning("register_places_missing", hint="python -m app.cli load-places")
        return None
    changed = await apply_geocoding(db, parse_places(dataset.content))
    logger.info("register_geocoded", version=dataset.version, placed=changed)
    return changed


async def load_company_dataset(
    db: AsyncSession,
    content: bytes | IO[bytes],
    *,
    version: str,
    source: str,
    enabled: bool,
) -> tuple[CompanyDataset, int]:
    """Retain a monthly bulk file as a reduced index; apply it only with the explicit
    register flag enabled. Caller owns commit/rollback. Duplicate names are rejected across
    the entire file."""
    index = build_company_index(content, await _sponsor_names(db))
    if not index.rows:
        raise ValueError("Empty Companies House file refused")
    dataset = CompanyDataset(
        version=version,
        source=source,
        sha256=index.sha256,
        row_count=index.rows,
        content=index.content,
    )
    db.add(dataset)
    await db.flush()
    matched = await apply_companies_match(
        db, index.companies, enabled=enabled, dataset_id=dataset.id, refresh=True
    )
    return dataset, matched


async def match_from_latest_dataset(db: AsyncSession, *, enabled: bool) -> int | None:
    if not enabled:
        return 0
    dataset = await db.scalar(
        select(CompanyDataset)
        .order_by(CompanyDataset.loaded_at.desc(), CompanyDataset.id.desc())
        .limit(1)
    )
    if dataset is None:
        logger.warning("register_companies_missing", hint="python -m app.cli load-companies")
        return None
    matched = await apply_companies_match(
        db,
        parse_company_index(dataset.content, await _sponsor_names(db)),
        enabled=True,
        dataset_id=dataset.id,
    )
    logger.info("register_companies_matched", version=dataset.version, matched=matched)
    return matched
