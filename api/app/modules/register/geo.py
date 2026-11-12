"""Town -> ITL1 region from the ONS Index of Place Names bulk file, plus the optional
Companies House (Free Company Data Product) match. Pure functions: no network, and the
caller supplies the downloaded bytes."""

from __future__ import annotations

import csv
import hashlib
import io
import re
from typing import TYPE_CHECKING, NamedTuple

from sqlalchemy import select

from app.core.logging import get_logger
from app.modules.register.ingest import normalise
from app.modules.register.models import CompanyDataset, CompanyMatch, PlaceDataset, Sponsor

if TYPE_CHECKING:
    import uuid

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
    return exact


def _ons_region(row: dict[str, str], code_cols: list[str], name_cols: list[str]) -> str | None:
    for col in code_cols:
        code = row.get(col, "").strip().upper()
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
    county spelling, so a sponsor's county can match the current, historic or ceremonial name."""
    text = content.decode("utf-8-sig")
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
    region_codes = cols(r"rgn\d{2}cd") + cols(r"ctry\d{2}cd")
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
        for county in {values[c].strip() for c in counties} or {""}:
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


def parse_companies(content: bytes) -> dict[str, tuple[str, str | None]]:
    """normalised company name -> (number, SIC section). Names that occur twice are dropped:
    a bulk match must never guess between two companies."""
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    needed = {"CompanyName", "CompanyNumber", "SICCode.SicText_1"}
    if not needed <= {(h or "").strip() for h in reader.fieldnames or ()}:
        raise ValueError("Unexpected Companies House CSV columns")
    found: dict[str, tuple[str, str | None]] = {}
    clash: set[str] = set()
    for raw in reader:
        row = {(k or "").strip(): v or "" for k, v in raw.items()}
        key = normalise(row["CompanyName"])
        if not key:
            continue
        if key in found:
            clash.add(key)
        found[key] = (row["CompanyNumber"].strip(), sic_section(row["SICCode.SicText_1"]))
    return {k: v for k, v in found.items() if k not in clash}


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
    db: AsyncSession, content: bytes, *, version: str, source: str, enabled: bool
) -> tuple[CompanyDataset, int]:
    """Retain a monthly bulk file; apply it only with the explicit register flag enabled.
    Caller owns commit/rollback. Duplicate names are rejected across the entire file."""
    companies = parse_companies(content)
    if not companies:
        raise ValueError("Empty or wholly ambiguous Companies House file refused")
    dataset = CompanyDataset(
        version=version,
        source=source,
        sha256=hashlib.sha256(content).hexdigest(),
        row_count=len(companies),
        content=content,
    )
    db.add(dataset)
    await db.flush()
    matched = await apply_companies_match(
        db, companies, enabled=enabled, dataset_id=dataset.id, refresh=True
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
        db, parse_companies(dataset.content), enabled=True, dataset_id=dataset.id
    )
    logger.info("register_companies_matched", version=dataset.version, matched=matched)
    return matched
