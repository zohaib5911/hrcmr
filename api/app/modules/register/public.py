"""Public sponsor register pages (plan 8.x, T20.4, R5): regions, change bulletins, profiles,
sitemap ids and the "report a problem" form. No login.

Everything here reads the global register tables, which hold published government data only. The
report form is the one POST: it checks a rate limit and Turnstile, and stores the message with a
hash of the connection, never the address."""

from __future__ import annotations

import re
import uuid  # noqa: TC003 (Pydantic resolves response fields at runtime)
from datetime import date, timedelta
from statistics import median
from typing import TYPE_CHECKING, Annotated, Literal

from fastapi import APIRouter, Path, Query, Request
from pydantic import BaseModel, EmailStr, Field, StringConstraints
from sqlalchemy import distinct, func, or_, select, tuple_
from sqlalchemy.orm import aliased

from app.core.errors import AppError, NotFoundError
from app.core.rate_limit import RateLimiter, hashed
from app.core.schemas import RequestModel
from app.db.ids import uuid7
from app.db.session import GlobalDb  # noqa: TC001  (FastAPI reads the dependency at runtime)
from app.modules.auth.deps import client_ip
from app.modules.register.geo import ITL1_REGIONS
from app.modules.register.models import (
    Change,
    Entry,
    PossibleMatch,
    ProblemReport,
    Publication,
    Sponsor,
)
from app.modules.soc.public_router import SEARCH_PER_CONNECTION, _limit

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import InstrumentedAttribute
    from sqlalchemy.sql.elements import ColumnElement
    from sqlalchemy.sql.selectable import Subquery

router = APIRouter(prefix="/public/register", tags=["public-register"])
REPORT_PER_CONNECTION = ("public.register.report", 5, 3600)  # reports, per hour
SITEMAP_PAGE = 45_000
BULLETIN_LIMIT = 500


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "sponsor"


REGION_BY_SLUG = {slugify(r): r for r in ITL1_REGIONS}


class RegionTown(BaseModel):
    town: str
    count: int


class RegionChange(BaseModel):
    stable_id: str
    name: str
    town: str
    change: str


class RegionOut(BaseModel):
    region: str
    slug: str
    sponsors: int
    towns: list[RegionTown]
    routes: list[RegionTown]
    latest_changes: list[RegionChange]
    last_published: date | None


class RegionSummary(BaseModel):
    region: str
    slug: str
    sponsors: int


class RegionListOut(BaseModel):
    regions: list[RegionSummary]


class BulletinSummary(BaseModel):
    date: date
    added: int
    removed: int
    returned: int
    net: int


class BulletinListOut(BaseModel):
    bulletins: list[BulletinSummary]


class BulletinSponsor(BaseModel):
    stable_id: str
    slug: str
    name: str
    town: str
    region: str | None


class BulletinOut(BaseModel):
    date: date
    added: int
    removed: int
    returned: int
    net: int
    median_added_last_28: float | None
    regions: list[RegionTown]
    added_list: list[BulletinSponsor]
    removed_list: list[BulletinSponsor]
    returned_list: list[BulletinSponsor]
    possibly_same: list[str]
    truncated: bool


class ProfileEntry(BaseModel):
    type_rating: str
    route: str


class ProfileChange(BaseModel):
    date: date
    change: str
    detail: dict[str, object]


class ProfileOut(BaseModel):
    stable_id: str
    slug: str
    name: str
    town: str
    county: str
    region: str | None
    region_slug: str | None
    current: bool
    first_seen_on: date
    last_seen_on: date
    entries: list[ProfileEntry]
    changes: list[ProfileChange]


class SitemapItem(BaseModel):
    stable_id: str
    slug: str
    last_seen_on: date


class SitemapOut(BaseModel):
    items: list[SitemapItem]


class SitemapCountOut(BaseModel):
    pages: int


class ReportIn(RequestModel):
    sponsor_id: Annotated[str, StringConstraints(max_length=32)] | None = None
    email: EmailStr | None = None
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    turnstile_token: Annotated[str, StringConstraints(min_length=1, max_length=2048)]


class ReportOut(BaseModel):
    received: bool


async def _latest(db: GlobalDb) -> Publication | None:
    return await db.scalar(
        select(Publication)
        .order_by(Publication.published_on.desc(), Publication.id.desc())
        .limit(1)
    )


@router.get("/regions", response_model=RegionListOut)
async def list_regions(db: GlobalDb) -> RegionListOut:
    result = await db.execute(
        select(Sponsor.region_itl1, func.count())
        .where(Sponsor.current, Sponsor.region_itl1.is_not(None))
        .group_by(Sponsor.region_itl1)
    )
    rows = dict(result.all())
    return RegionListOut(
        regions=[
            RegionSummary(region=r, slug=slugify(r), sponsors=rows.get(r, 0)) for r in ITL1_REGIONS
        ]
    )


@router.get("/regions/{slug}", response_model=RegionOut)
async def region(slug: Annotated[str, Path(max_length=60)], db: GlobalDb) -> RegionOut:
    name = REGION_BY_SLUG.get(slug)
    if name is None:
        raise NotFoundError("Region not found.")
    in_region = (Sponsor.current, Sponsor.region_itl1 == name)
    total = await db.scalar(select(func.count()).select_from(Sponsor).where(*in_region)) or 0
    towns = await db.execute(
        select(Sponsor.town, func.count().label("n"))
        .where(*in_region)
        .group_by(Sponsor.town)
        .order_by(func.count().desc(), Sponsor.town)
        .limit(20)
    )
    latest = await _latest(db)
    routes: list[RegionTown] = []
    changes: list[RegionChange] = []
    if latest:
        routes = [
            RegionTown(town=r, count=n)
            for r, n in (
                await db.execute(
                    select(Entry.route, func.count(func.distinct(Entry.sponsor_id)).label("n"))
                    .join(Sponsor, Sponsor.id == Entry.sponsor_id)
                    .where(Entry.publication_id == latest.id, Sponsor.region_itl1 == name)
                    .group_by(Entry.route)
                    .order_by(func.count(func.distinct(Entry.sponsor_id)).desc(), Entry.route)
                )
            )
        ]
        changes = [
            RegionChange(stable_id=s.stable_id, name=s.organisation_name, town=s.town, change=c)
            for s, c in (
                await db.execute(
                    select(Sponsor, Change.change)
                    .join(Change, Change.sponsor_id == Sponsor.id)
                    .where(
                        Change.publication_id == latest.id,
                        Sponsor.region_itl1 == name,
                        Change.change.in_(("added", "removed", "returned")),
                    )
                    .order_by(Sponsor.organisation_name)
                    .limit(50)
                )
            )
        ]
    return RegionOut(
        region=name,
        slug=slug,
        sponsors=total,
        towns=[RegionTown(town=t, count=n) for t, n in towns],
        routes=routes,
        latest_changes=changes,
        last_published=latest.published_on if latest else None,
    )


async def _counts(db: GlobalDb) -> dict[object, dict[str, int]]:
    out: dict[object, dict[str, int]] = {}
    rows = await db.execute(
        select(Change.publication_id, Change.change, func.count())
        .where(Change.change.in_(("added", "removed", "returned")))
        .group_by(Change.publication_id, Change.change)
    )
    for pub, kind, n in rows:
        out.setdefault(pub, {})[kind] = n
    return out


@router.get("/changes", response_model=BulletinListOut)
async def list_bulletins(
    db: GlobalDb, limit: Annotated[int, Query(ge=1, le=200)] = 60
) -> BulletinListOut:
    pubs = (
        await db.scalars(select(Publication).order_by(Publication.published_on.desc()).limit(limit))
    ).all()
    counts = await _counts(db)
    bulletins = []
    for p in pubs:
        c = counts.get(p.id, {})
        a, r, ret = c.get("added", 0), c.get("removed", 0), c.get("returned", 0)
        bulletins.append(
            BulletinSummary(date=p.published_on, added=a, removed=r, returned=ret, net=a + ret - r)
        )
    return BulletinListOut(bulletins=bulletins)


def _sponsor(s: Sponsor) -> BulletinSponsor:
    return BulletinSponsor(
        stable_id=s.stable_id,
        slug=slugify(s.organisation_name),
        name=s.organisation_name,
        town=s.town,
        region=s.region_itl1,
    )


@router.get("/changes/{on}", response_model=BulletinOut)
async def bulletin(on: date, db: GlobalDb) -> BulletinOut:
    pub = await db.scalar(
        select(Publication)
        .where(Publication.published_on == on)
        .order_by(Publication.fetched_at.desc())
        .limit(1)
    )
    if pub is None:
        raise NotFoundError("No bulletin for that date.")
    rows = (
        await db.execute(
            select(Sponsor, Change.change)
            .join(Change, Change.sponsor_id == Sponsor.id)
            .where(
                Change.publication_id == pub.id,
                Change.change.in_(("added", "removed", "returned")),
            )
            .order_by(Sponsor.organisation_name)
        )
    ).all()
    lists: dict[str, list[BulletinSponsor]] = {"added": [], "removed": [], "returned": []}
    regions: dict[str, int] = {}
    totals = {"added": 0, "removed": 0, "returned": 0}
    for s, kind in rows:
        totals[kind] += 1
        if len(lists[kind]) < BULLETIN_LIMIT:
            lists[kind].append(_sponsor(s))
        if kind != "removed" and s.region_itl1:
            regions[s.region_itl1] = regions.get(s.region_itl1, 0) + 1
    earlier = (
        await db.scalars(
            select(Publication.id)
            .where(Publication.published_on < on)
            .order_by(Publication.published_on.desc())
            .limit(28)
        )
    ).all()
    counts = await _counts(db)
    base = [counts.get(i, {}).get("added", 0) for i in earlier]
    pairs = (
        await db.execute(
            select(PossibleMatch.added_sponsor_id, PossibleMatch.removed_sponsor_id).where(
                PossibleMatch.added_sponsor_id.in_(
                    select(Change.sponsor_id).where(Change.publication_id == pub.id)
                )
            )
        )
    ).all()
    names = {
        s.id: s.organisation_name
        for s in (
            await db.scalars(
                select(Sponsor).where(Sponsor.id.in_([i for pair in pairs for i in pair]))
            )
        ).all()
    }
    return BulletinOut(
        date=on,
        added=totals["added"],
        removed=totals["removed"],
        returned=totals["returned"],
        net=totals["added"] + totals["returned"] - totals["removed"],
        median_added_last_28=float(median(base)) if base else None,
        regions=[
            RegionTown(town=r, count=n)
            for r, n in sorted(regions.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        added_list=lists["added"],
        removed_list=lists["removed"],
        returned_list=lists["returned"],
        possibly_same=[f"{names[a]} may be the same sponsor as {names[r]}" for a, r in pairs],
        truncated=any(totals[k] > BULLETIN_LIMIT for k in totals),
    )


@router.get("/sponsors/{stable_id}", response_model=ProfileOut)
async def profile(
    stable_id: Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")], db: GlobalDb
) -> ProfileOut:
    s = await db.scalar(select(Sponsor).where(Sponsor.stable_id == stable_id))
    if s is None:
        raise NotFoundError("Sponsor not found.")
    latest = await db.scalar(
        select(Publication.id)
        .join(Entry, Entry.publication_id == Publication.id)
        .where(Entry.sponsor_id == s.id)
        .order_by(Publication.published_on.desc())
        .limit(1)
    )
    entries = (
        (
            await db.scalars(
                select(Entry)
                .where(Entry.sponsor_id == s.id, Entry.publication_id == latest)
                .order_by(Entry.route, Entry.type_rating)
            )
        ).all()
        if latest
        else []
    )
    changes = await db.execute(
        select(Publication.published_on, Change.change, Change.detail)
        .join(Publication, Publication.id == Change.publication_id)
        .where(Change.sponsor_id == s.id)
        .order_by(Publication.published_on.desc())
        .limit(100)
    )
    return ProfileOut(
        stable_id=s.stable_id,
        slug=slugify(s.organisation_name),
        name=s.organisation_name,
        town=s.town,
        county=s.county,
        region=s.region_itl1,
        region_slug=slugify(s.region_itl1) if s.region_itl1 else None,
        current=s.current,
        first_seen_on=s.first_seen_on,
        last_seen_on=s.last_seen_on,
        entries=[ProfileEntry(type_rating=e.type_rating, route=e.route) for e in entries],
        changes=[ProfileChange(date=d, change=c, detail=det) for d, c, det in changes],
    )


@router.get("/sitemap", response_model=SitemapCountOut)
async def sitemap_count(db: GlobalDb) -> SitemapCountOut:
    total = await db.scalar(select(func.count()).select_from(Sponsor)) or 0
    return SitemapCountOut(pages=max(1, -(-total // SITEMAP_PAGE)))


@router.get("/sitemap/{page}", response_model=SitemapOut)
async def sitemap_page(page: Annotated[int, Path(ge=0, le=1000)], db: GlobalDb) -> SitemapOut:
    rows = await db.execute(
        select(Sponsor.stable_id, Sponsor.organisation_name, Sponsor.last_seen_on)
        .order_by(Sponsor.id)
        .offset(page * SITEMAP_PAGE)
        .limit(SITEMAP_PAGE)
    )
    return SitemapOut(
        items=[SitemapItem(stable_id=i, slug=slugify(n), last_seen_on=d) for i, n, d in rows]
    )


@router.post("/reports", response_model=ReportOut, status_code=201)
async def report_problem(body: ReportIn, db: GlobalDb, request: Request) -> ReportOut:
    ip = client_ip(request)
    auth = request.app.state.auth
    name, limit, window = REPORT_PER_CONNECTION
    result = await RateLimiter(auth.redis).hit(
        name, ip or "unknown", limit=limit, window_seconds=window
    )
    if not result.allowed:
        raise AppError(
            "RATE_LIMITED",
            "Too many reports from this connection. Try again later.",
            status_code=429,
        )
    if not await auth.turnstile.verify(body.turnstile_token, ip):
        raise AppError(
            "TURNSTILE_FAILED",
            "We could not confirm you are a person. Try again.",
            status_code=400,
            field="turnstile_token",
        )
    db.add(
        ProblemReport(
            id=uuid7(),
            sponsor_stable_id=body.sponsor_id,
            email=str(body.email).strip().lower() if body.email else None,
            message=body.message,
            ip_hash=hashed(ip) if ip else None,
        )
    )
    await db.commit()
    return ReportOut(received=True)


class ExploreQuery(RequestModel):
    q: str = Field(default="", max_length=100)
    region: str = Field(default="", max_length=100)
    route: str = Field(default="", max_length=300)
    rating: str = Field(default="", max_length=300)
    industry: str = Field(default="", max_length=10)
    published_on: date | None = None
    publication_id: uuid.UUID | None = None
    window: Literal["7", "30", "90", "180", "365", "start"] = "30"
    page: int = Field(default=1, ge=1, le=10000)


class PublicationOut(BaseModel):
    id: uuid.UUID
    published_on: date
    source_url: str


class Bucket(BaseModel):
    label: str
    count: int


class SponsorOut(BaseModel):
    id: str
    name: str
    town: str
    region: str | None
    industry: str | None
    precision: str
    first_seen: date
    routes: list[str]
    ratings: list[str]


class PulsePoint(BaseModel):
    published_on: date
    count: int
    added: int
    removed: int


class ExploreOut(BaseModel):
    publications: list[PublicationOut] = Field(default_factory=list)
    selected: PublicationOut | None = None
    baseline: PublicationOut | None = None
    total: int = 0
    previous_total: int = 0
    page: int = 1
    page_size: int = 50
    results: list[SponsorOut] = Field(default_factory=list)
    newest: list[SponsorOut] = Field(default_factory=list)
    facets: dict[str, list[str]] = Field(default_factory=dict)
    sections: dict[str, list[Bucket]] = Field(default_factory=dict)
    previous_regions: list[Bucket] = Field(default_factory=list)
    daily_previous_regions: list[Bucket] = Field(default_factory=list)
    timeline: list[PulsePoint] = Field(default_factory=list)


def conditions(query: ExploreQuery) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = []
    if query.q.strip():
        q = query.q.strip()
        clauses.append(
            or_(
                Sponsor.organisation_name.icontains(q, autoescape=True),
                Sponsor.town.icontains(q, autoescape=True),
                Entry.route.icontains(q, autoescape=True),
            )
        )
    for value, column in (
        (query.region, Sponsor.region_itl1),
        (query.route, Entry.route),
        (query.rating, Entry.type_rating),
        (query.industry, Sponsor.sic_section),
    ):
        if value:
            clauses.append(column == value)
    return clauses


def snapshot(publication_id: uuid.UUID, query: ExploreQuery) -> Subquery:
    # Match sponsors first, then show all their entries in the selected publication. Multiple
    # routes never inflate the sponsor count. Never use the mutable Sponsor.current flag here.
    return (
        select(Entry.sponsor_id)
        .join(Sponsor, Sponsor.id == Entry.sponsor_id)
        .where(Entry.publication_id == publication_id, *conditions(query))
        .distinct()
        .subquery()
    )


async def buckets(
    db: AsyncSession,
    ids: Subquery,
    column: InstrumentedAttribute[str] | InstrumentedAttribute[str | None],
) -> list[Bucket]:
    label = func.coalesce(func.nullif(column, ""), "Unknown")
    rows = await db.execute(
        select(label, func.count(distinct(Sponsor.id)))
        .select_from(Sponsor)
        .join(ids, ids.c.sponsor_id == Sponsor.id)
        .group_by(label)
        .order_by(func.count(distinct(Sponsor.id)).desc(), label)
        .limit(50)
    )
    return [Bucket(label=name, count=count) for name, count in rows]


async def sponsors(
    db: AsyncSession,
    ids: Subquery,
    publication_id: uuid.UUID,
    *,
    offset: int = 0,
    newest: bool = False,
) -> list[SponsorOut]:
    order = [Sponsor.first_seen_on.desc()] if newest else []
    rows = (
        await db.scalars(
            select(Sponsor)
            .join(ids, ids.c.sponsor_id == Sponsor.id)
            .order_by(*order, Sponsor.organisation_name, Sponsor.id)
            .offset(offset)
            .limit(10 if newest else 50)
        )
    ).all()
    if not rows:
        return []
    entries = (
        await db.scalars(
            select(Entry).where(
                Entry.publication_id == publication_id, Entry.sponsor_id.in_([s.id for s in rows])
            )
        )
    ).all()
    return [
        SponsorOut(
            id=s.stable_id,
            name=s.organisation_name,
            town=s.town,
            region=s.region_itl1,
            industry=s.sic_section,
            precision=s.place_precision,
            first_seen=s.first_seen_on,
            routes=sorted({e.route for e in entries if e.sponsor_id == s.id}),
            ratings=sorted({e.type_rating for e in entries if e.sponsor_id == s.id}),
        )
        for s in rows
    ]


async def explore_data(db: AsyncSession, query: ExploreQuery) -> ExploreOut:
    pubs = list(
        (
            await db.scalars(
                select(Publication)
                .where(Publication.status == "complete")
                .order_by(Publication.published_on, Publication.fetched_at, Publication.id)
            )
        ).all()
    )
    out = ExploreOut(
        publications=[
            PublicationOut(id=p.id, published_on=p.published_on, source_url=p.source_url)
            for p in pubs
        ],
        page=query.page,
    )
    eligible = [
        i
        for i, p in enumerate(pubs)
        if query.published_on is None or p.published_on <= query.published_on
    ]
    if query.publication_id is not None:
        eligible = [i for i, p in enumerate(pubs) if p.id == query.publication_id]
    if not eligible:
        return out
    index = eligible[-1]
    selected = pubs[index]
    target = (
        pubs[0].published_on
        if query.window == "start"
        else selected.published_on - timedelta(days=int(query.window))
    )
    prior = [i for i in range(index + 1) if pubs[i].published_on <= target]
    baseline_index = prior[-1] if prior else 0
    baseline = pubs[baseline_index]
    out.selected, out.baseline = out.publications[index], out.publications[baseline_index]
    ids, before = snapshot(selected.id, query), snapshot(baseline.id, query)
    out.total = int(await db.scalar(select(func.count()).select_from(ids)) or 0)
    out.previous_total = int(await db.scalar(select(func.count()).select_from(before)) or 0)
    out.results = await sponsors(db, ids, selected.id, offset=(query.page - 1) * 50)
    out.newest = await sponsors(db, ids, selected.id, newest=True)
    for name, column in (
        ("towns", Sponsor.town),
        ("regions", Sponsor.region_itl1),
        ("precision", Sponsor.place_precision),
        ("industries", Sponsor.sic_section),
    ):
        out.sections[name] = await buckets(db, ids, column)
    out.previous_regions = await buckets(db, before, Sponsor.region_itl1)
    daily_prior = [p for p in pubs[:index] if p.published_on < selected.published_on]
    daily_id = daily_prior[-1].id if daily_prior else selected.id
    out.daily_previous_regions = await buckets(db, snapshot(daily_id, query), Sponsor.region_itl1)
    # Reference facets ignore filters, so a user can always change to another available value.
    for name, column in (
        ("region", Sponsor.region_itl1),
        ("route", Entry.route),
        ("rating", Entry.type_rating),
        ("industry", Sponsor.sic_section),
    ):
        values = await db.scalars(
            select(column)
            .select_from(Entry)
            .join(Sponsor, Sponsor.id == Entry.sponsor_id)
            .where(Entry.publication_id == selected.id, column.is_not(None), column != "")
            .distinct()
            .order_by(column)
        )
        out.facets[name] = [value for value in values if value is not None]
    for name, entry_column in (
        ("routes", Entry.route),
        ("ratings", Entry.type_rating),
        ("types", func.split_part(Entry.type_rating, " (", 1)),
    ):
        rows = await db.execute(
            select(entry_column, func.count(distinct(Entry.sponsor_id)))
            .join(ids, ids.c.sponsor_id == Entry.sponsor_id)
            .where(Entry.publication_id == selected.id)
            .group_by(entry_column)
            .order_by(func.count(distinct(Entry.sponsor_id)).desc(), entry_column)
        )
        out.sections[name] = [
            Bucket(label=label or "Unknown", count=count) for label, count in rows
        ]
    # One grouped query over the window, rather than one snapshot read for each chart point.
    history_ids = [p.id for p in pubs[baseline_index : index + 1]]
    counts = dict(
        (
            await db.execute(
                select(Entry.publication_id, func.count(distinct(Entry.sponsor_id)))
                .join(Sponsor, Sponsor.id == Entry.sponsor_id)
                .where(Entry.publication_id.in_(history_ids), *conditions(query))
                .group_by(Entry.publication_id)
            )
        ).all()
    )
    # Removed entries belong to the preceding snapshot, not the new one. An EXISTS matches the
    # filters against either side of a change without discarding removed sponsors.
    previous, current = aliased(Publication), aliased(Publication)
    previous_id = (
        select(previous.id)
        .join(current, current.id == Change.publication_id)
        .where(
            previous.status == "complete",
            tuple_(previous.published_on, previous.fetched_at, previous.id)
            < tuple_(current.published_on, current.fetched_at, current.id),
        )
        .order_by(previous.published_on.desc(), previous.fetched_at.desc(), previous.id.desc())
        .limit(1)
        .correlate(Change)
        .scalar_subquery()
    )
    match = (
        select(Entry.id)
        .join(Sponsor, Sponsor.id == Entry.sponsor_id)
        .where(
            Entry.sponsor_id == Change.sponsor_id,
            or_(Entry.publication_id == Change.publication_id, Entry.publication_id == previous_id),
            *conditions(query),
        )
        .correlate(Change)
        .exists()
    )
    changes = (
        await db.execute(
            select(Change.publication_id, Change.change, func.count())
            .where(
                Change.publication_id.in_(history_ids),
                match,
                Change.change.in_(["added", "returned", "removed"]),
            )
            .group_by(Change.publication_id, Change.change)
        )
    ).all()
    change_counts = {(pid, kind): n for pid, kind, n in changes}
    out.timeline = [
        PulsePoint(
            published_on=p.published_on,
            count=counts.get(p.id, 0),
            added=change_counts.get((p.id, "added"), 0) + change_counts.get((p.id, "returned"), 0),
            removed=change_counts.get((p.id, "removed"), 0),
        )
        for p in pubs[baseline_index : index + 1]
    ]
    return out


@router.get("/explore", response_model=ExploreOut)
async def explore(
    request: Request, db: GlobalDb, query: Annotated[ExploreQuery, Query()]
) -> ExploreOut:
    await _limit(request, ("public.register.explore", *SEARCH_PER_CONNECTION[1:]))
    return await explore_data(db, query)
