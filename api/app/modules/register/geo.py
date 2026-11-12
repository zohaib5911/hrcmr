"""Town -> ITL1 region from the ONS Index of Place Names bulk file, plus the optional
Companies House (Free Company Data Product) match. Pure functions: no network, and the
caller supplies the downloaded bytes."""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING, NamedTuple

from sqlalchemy import select

from app.modules.register.ingest import normalise
from app.modules.register.models import Sponsor

if TYPE_CHECKING:
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
    db: AsyncSession, companies: dict[str, tuple[str, str | None]], *, enabled: bool
) -> int:
    """Behind a flag: does nothing unless enabled. Exact normalised-name matches only."""
    if not enabled:
        return 0
    changed = 0
    for sponsor in (await db.scalars(select(Sponsor))).all():
        if sponsor.companies_house_number:
            continue
        hit = companies.get(sponsor.normalised_name)
        if hit:
            sponsor.companies_house_number, sponsor.sic_section = hit
            changed += 1
    await db.flush()
    return changed
