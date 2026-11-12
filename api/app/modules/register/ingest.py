"""Validated GOV.UK discovery and atomic, hash-idempotent sponsor snapshots."""

from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from collections import defaultdict
from datetime import date  # noqa: TC003
from difflib import SequenceMatcher
from html.parser import HTMLParser
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlsplit

from sqlalchemy import func, select

from app.modules.register.models import Change, Entry, PossibleMatch, Publication, Sponsor

if TYPE_CHECKING:
    import httpx
    from sqlalchemy.ext.asyncio import AsyncSession

PAGE = "https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers"
HOSTS = {"www.gov.uk", "assets.publishing.service.gov.uk"}
HEADERS = ("Organisation Name", "Town/City", "County", "Type & Rating", "Route")


def allowed(url: str) -> str:
    p = urlsplit(url)
    if (
        p.scheme != "https"
        or p.hostname not in HOSTS
        or p.port not in (None, 443)
        or p.username
        or p.password
    ):
        raise ValueError("Register source URL is not allowlisted")
    return url


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        href = dict(attrs).get("href")
        if tag == "a" and href and urlsplit(href).path.lower().endswith(".csv"):
            self.urls.append(allowed(urljoin(PAGE, href)))


def discover(html: str) -> str:
    parser = Links()
    parser.feed(html)
    if len(set(parser.urls)) != 1:
        raise ValueError("Expected one current sponsor CSV attachment")
    return parser.urls[0]


async def download(client: httpx.AsyncClient, url: str, limit: int) -> bytes:
    for _ in range(5):
        async with client.stream("GET", allowed(url), follow_redirects=False) as response:
            if response.is_redirect:
                url = allowed(urljoin(url, response.headers["location"]))
                continue
            response.raise_for_status()
            content = bytearray()
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content) > limit:
                    raise ValueError("Register response too large")
            return bytes(content)
    raise ValueError("Too many source redirects")


def normalise(value: str) -> str:
    return " ".join(
        re.sub(r"[^\w\s]", " ", unicodedata.normalize("NFKC", value).casefold()).split()
    )


def parse(content: bytes) -> dict[tuple[str, str, str], tuple[str, set[tuple[str, str]]]]:
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    if tuple(reader.fieldnames or ()) != HEADERS:
        raise ValueError("Unexpected register CSV columns")
    rows: dict[tuple[str, str, str], tuple[str, set[tuple[str, str]]]] = {}
    for row in reader:
        if None in row or any(row[h] is None for h in HEADERS):
            raise ValueError("Malformed register row")
        name, town, county, rating, route = (row[h].strip() for h in HEADERS)
        if not name or not rating or not route or max(map(len, (name, town, county))) > 500:
            raise ValueError("Invalid register row")
        key = (normalise(name), normalise(town), normalise(county))
        rows.setdefault(key, (name, set()))[1].add((rating, route))
    if not rows:
        raise ValueError("Empty register refused")
    return rows


async def ingest(db: AsyncSession, client: httpx.AsyncClient, on: date) -> str:
    html = await download(client, PAGE, 5_000_000)
    url = discover(html.decode("utf-8"))
    content = await download(client, url, 50_000_000)
    digest = hashlib.sha256(content).hexdigest()
    # Serialize snapshot writers, including manual reruns. Caller owns commit/rollback.
    await db.execute(select(func.pg_advisory_xact_lock(20201101)))
    if await db.scalar(select(Publication.id).where(Publication.sha256 == digest)):
        return "unchanged"
    rows = parse(content)
    previous = await db.scalar(select(Publication).order_by(Publication.fetched_at.desc()).limit(1))
    old: dict[object, set[tuple[str, str]]] = defaultdict(set)
    if previous:
        for entry in (
            await db.scalars(select(Entry).where(Entry.publication_id == previous.id))
        ).all():
            old[entry.sponsor_id].add((entry.type_rating, entry.route))
    sponsors = (await db.scalars(select(Sponsor))).all()
    by_key = {(s.normalised_name, s.town, s.county): s for s in sponsors}
    publication = Publication(
        published_on=on,
        source_url=url,
        row_count=sum(len(v[1]) for v in rows.values()),
        sha256=digest,
    )
    db.add(publication)
    await db.flush()
    added, removed = [], []

    def change(s: Sponsor, kind: str, detail: dict[str, object]) -> None:
        db.add(Change(publication_id=publication.id, sponsor_id=s.id, change=kind, detail=detail))

    for key, (name, entries) in rows.items():
        sponsor = by_key.get(key)
        fresh = sponsor is None
        if sponsor is None:
            sponsor = Sponsor(
                organisation_name=name,
                normalised_name=key[0],
                town=key[1],
                county=key[2],
                first_seen_on=on,
                last_seen_on=on,
                current=True,
            )
            db.add(sponsor)
            await db.flush()
        if sponsor.id not in old:
            change(sponsor, "added" if fresh else "returned", {})
            added.append(sponsor)
        else:
            before = old[sponsor.id]
            for route in {r for _, r in entries} - {r for _, r in before}:
                change(sponsor, "route_added", {"route": route})
            for route in {r for _, r in before} - {r for _, r in entries}:
                change(sponsor, "route_removed", {"route": route})
            for route in {r for _, r in before} & {r for _, r in entries}:
                a, b = (
                    sorted(t for t, r in before if r == route),
                    sorted(t for t, r in entries if r == route),
                )
                if a != b:
                    change(sponsor, "rating_changed", {"route": route, "before": a, "after": b})
        sponsor.current, sponsor.last_seen_on = True, on
        sponsor.organisation_name = name
        for rating, route in entries:
            db.add(
                Entry(
                    publication_id=publication.id,
                    sponsor_id=sponsor.id,
                    type_rating=rating,
                    route=route,
                )
            )
    for sponsor in sponsors:
        if sponsor.current and (sponsor.normalised_name, sponsor.town, sponsor.county) not in rows:
            sponsor.current = False
            removed.append(sponsor)
            change(sponsor, "removed", {})
    for new in added:
        for gone in removed:
            if (new.town, new.county) != (gone.town, gone.county):
                continue
            score = SequenceMatcher(None, new.normalised_name, gone.normalised_name).ratio()
            if score >= 0.85 and not await db.scalar(
                select(PossibleMatch.id).where(
                    PossibleMatch.added_sponsor_id == new.id,
                    PossibleMatch.removed_sponsor_id == gone.id,
                )
            ):
                db.add(
                    PossibleMatch(
                        added_sponsor_id=new.id,
                        removed_sponsor_id=gone.id,
                        similarity=score,
                        reason="Similar name in the same locality; requires review",
                    )
                )
    await db.flush()
    return "imported"
