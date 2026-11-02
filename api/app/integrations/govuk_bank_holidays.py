"""Bank holidays from GOV.UK (plan.md T4.5): the official list for each part of the UK.

``https://www.gov.uk/bank-holidays.json`` is the documented, keyless feed behind the GOV.UK page. It
is fetched by the weekly job, never on a visitor's request, and only that fixed address is called.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from app.core.logging import get_logger

logger = get_logger("app.bank_holidays")

SOURCE_URL = "https://www.gov.uk/bank-holidays.json"
TIMEOUT_SECONDS = 15.0
REGIONS = ("england-and-wales", "scotland", "northern-ireland")


class FeedError(Exception):
    """The feed could not be fetched or was not what it should be."""


@dataclass(frozen=True)
class Holiday:
    region: str
    on_date: date
    title: str


def parse(data: dict[str, Any]) -> list[Holiday]:
    found: list[Holiday] = []
    for region in REGIONS:
        events = (data.get(region) or {}).get("events")
        if not isinstance(events, list):
            raise FeedError(f"no events for {region}")
        for event in events:
            try:
                found.append(
                    Holiday(region, date.fromisoformat(event["date"]), str(event["title"])[:120])
                )
            except (KeyError, ValueError, TypeError) as exc:
                raise FeedError("an event was not readable") from exc
    return found


async def fetch(client: httpx.AsyncClient | None = None) -> list[Holiday]:
    own = client is None
    http = client or httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=False)
    try:
        response = await http.get(SOURCE_URL, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        return parse(response.json())
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("bank_holidays_unavailable", kind=type(exc).__name__)
        raise FeedError("the bank holidays feed did not answer") from exc
    finally:
        if own:
            await http.aclose()
