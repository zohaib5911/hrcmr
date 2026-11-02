"""Companies House lookup (plan.md 8.15): type a registered number, get the name and address.

The public Companies House API is called from the server with our key, never from the browser.
It is optional: with no key the feature is off and the form has no lookup button.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx

from app.core.logging import get_logger
from app.modules.companies.reference import COMPANIES_HOUSE_TYPES

if TYPE_CHECKING:
    from app.core.config import Settings

logger = get_logger("app.companies_house")

BASE_URL = "https://api.company-information.service.gov.uk"
TIMEOUT_SECONDS = 6.0
NUMBER = re.compile(r"[A-Z0-9]{8}")


class CompaniesHouseError(Exception):
    """The lookup could not be completed. ``found`` is False when the number does not exist."""

    def __init__(self, *, found: bool) -> None:
        super().__init__("lookup failed")
        self.found = found


@dataclass(frozen=True)
class Address:
    line1: str | None
    line2: str | None
    city: str | None
    county: str | None
    postcode: str | None
    country: str | None


@dataclass(frozen=True)
class CompanyRecord:
    number: str
    name: str
    status: str | None
    legal_structure: str | None
    address: Address


def normalise_number(raw: str) -> str | None:
    """The 8-character form Companies House uses (``1234567`` becomes ``01234567``), or None."""
    value = raw.strip().upper().replace(" ", "")
    if value.isdigit() and len(value) < 8:
        value = value.zfill(8)
    return value if NUMBER.fullmatch(value) else None


def parse_record(number: str, data: dict[str, Any]) -> CompanyRecord:
    office = data.get("registered_office_address") or {}
    return CompanyRecord(
        number=number,
        name=str(data.get("company_name", "")).strip(),
        status=data.get("company_status"),
        legal_structure=COMPANIES_HOUSE_TYPES.get(str(data.get("type", "")), "other"),
        address=Address(
            line1=office.get("address_line_1"),
            line2=office.get("address_line_2"),
            city=office.get("locality"),
            county=office.get("region"),
            postcode=office.get("postal_code"),
            country=office.get("country"),
        ),
    )


class CompaniesHouse:
    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        self._auth = httpx.BasicAuth(api_key, "")  # the key is the user name, the password is blank
        self._client = client

    @classmethod
    def from_settings(cls, settings: Settings) -> CompaniesHouse | None:
        key = settings.companies_house_api_key
        return cls(key.get_secret_value()) if key else None

    async def lookup(self, number: str) -> CompanyRecord:
        client = self._client or httpx.AsyncClient(timeout=TIMEOUT_SECONDS)
        try:
            response = await client.get(
                f"{BASE_URL}/company/{number}", auth=self._auth, timeout=TIMEOUT_SECONDS
            )
        except httpx.HTTPError as exc:
            logger.warning("companies_house_unreachable")
            raise CompaniesHouseError(found=True) from exc
        finally:
            if self._client is None:
                await client.aclose()
        if response.status_code == 404:
            raise CompaniesHouseError(found=False)
        if response.status_code != 200:
            logger.warning("companies_house_error", status=response.status_code)
            raise CompaniesHouseError(found=True)
        return parse_record(number, response.json())
