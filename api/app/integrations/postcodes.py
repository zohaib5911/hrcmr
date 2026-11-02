"""Postcode lookup with postcodes.io (plan.md 8.15): type a postcode, get the town and county.

A free public service with no key. The address of the service is fixed here, so no one can make
the server fetch an address of their choosing; only the postcode, checked against the UK format,
is sent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.logging import get_logger

logger = get_logger("app.postcodes")

BASE_URL = "https://api.postcodes.io/postcodes"
TIMEOUT_SECONDS = 5.0
_POSTCODE = re.compile(r"([A-Z]{1,2}[0-9][A-Z0-9]?)\s*([0-9][A-Z]{2})")


class PostcodeError(Exception):
    """``found`` is False when the postcode does not exist, True when the service did not answer."""

    def __init__(self, *, found: bool) -> None:
        super().__init__("postcode lookup failed")
        self.found = found


@dataclass(frozen=True)
class PostcodeInfo:
    postcode: str
    city: str | None
    county: str | None
    country: str | None


def normalise_postcode(raw: str) -> str | None:
    """``sw1a1aa`` becomes ``SW1A 1AA``; anything that is not a UK postcode is None."""
    match = _POSTCODE.fullmatch(raw.strip().upper())
    return f"{match.group(1)} {match.group(2)}" if match else None


def parse(postcode: str, data: dict[str, Any]) -> PostcodeInfo:
    result = data.get("result") or {}
    return PostcodeInfo(
        postcode=postcode,
        city=result.get("admin_district") or result.get("parish"),
        county=result.get("admin_county"),
        country=result.get("country"),
    )


class Postcodes:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def lookup(self, postcode: str) -> PostcodeInfo:
        client = self._client or httpx.AsyncClient(timeout=TIMEOUT_SECONDS)
        try:
            response = await client.get(
                f"{BASE_URL}/{postcode.replace(' ', '')}", timeout=TIMEOUT_SECONDS
            )
        except httpx.HTTPError as exc:
            logger.warning("postcodes_unreachable")
            raise PostcodeError(found=True) from exc
        finally:
            if self._client is None:
                await client.aclose()
        if response.status_code == 404:
            raise PostcodeError(found=False)
        if response.status_code != 200:
            logger.warning("postcodes_error", status=response.status_code)
            raise PostcodeError(found=True)
        return parse(postcode, response.json())
