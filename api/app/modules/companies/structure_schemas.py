"""What ``/locations``, ``/departments`` and ``/designations`` accept and return (plan.md 8.15)."""

from __future__ import annotations

import re
import uuid  # noqa: TC003  (pydantic resolves the annotations at runtime)
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.integrations.postcodes import normalise_postcode

Text120 = Annotated[str, Field(min_length=1, max_length=120)]
OptionalText120 = Annotated[str, Field(max_length=120)] | None


def _clean(value: object) -> object:
    return value.strip() or None if isinstance(value, str) else value


class _Strict(BaseModel):
    """Fields we do not know are refused, not ignored (a form cannot slip in an extra field)."""

    model_config = ConfigDict(extra="forbid")


# --- locations -----------------------------------------------------------------------------------


class LocationOut(BaseModel):
    id: uuid.UUID
    name: str
    postcode: str
    address_line1: str
    address_line2: str | None
    address_line3: str | None
    city: str
    county: str | None
    country: str
    is_default: bool


class LocationIn(_Strict):
    name: Text120
    postcode: str
    address_line1: Text120
    address_line2: OptionalText120 = None
    address_line3: OptionalText120 = None
    city: Annotated[str, Field(min_length=1, max_length=80)]
    county: Annotated[str, Field(max_length=80)] | None = None
    country: Annotated[str, Field(min_length=1, max_length=60)] = "United Kingdom"
    is_default: bool = False

    _trim = field_validator(
        "name",
        "address_line1",
        "address_line2",
        "address_line3",
        "city",
        "county",
        "country",
        mode="before",
    )(_clean)

    @field_validator("postcode")
    @classmethod
    def _postcode(cls, value: str) -> str:
        postcode = normalise_postcode(value)
        if postcode is None:
            raise ValueError("Enter a UK postcode, such as SW1A 1AA.")
        return postcode


class LocationPatch(_Strict):
    """Only the fields that are sent change."""

    name: Text120 | None = None
    postcode: str | None = None
    address_line1: Text120 | None = None
    address_line2: OptionalText120 = None
    address_line3: OptionalText120 = None
    city: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    county: Annotated[str, Field(max_length=80)] | None = None
    country: Annotated[str, Field(min_length=1, max_length=60)] | None = None
    is_default: bool | None = None

    _trim = field_validator(
        "name",
        "address_line1",
        "address_line2",
        "address_line3",
        "city",
        "county",
        "country",
        mode="before",
    )(_clean)

    @field_validator("postcode")
    @classmethod
    def _postcode(cls, value: str | None) -> str | None:
        if value is None:
            return None
        postcode = normalise_postcode(value)
        if postcode is None:
            raise ValueError("Enter a UK postcode, such as SW1A 1AA.")
        return postcode


class PostcodeOut(BaseModel):
    postcode: str
    city: str | None
    county: str | None
    country: str | None


# --- departments and designations -------------------------------------------------------------


class DepartmentOut(BaseModel):
    id: uuid.UUID
    name: str
    designations: int = Field(description="How many job titles it has.")


class DepartmentIn(_Strict):
    name: Annotated[str, Field(min_length=1, max_length=100)]

    _trim = field_validator("name", mode="before")(_clean)


class DesignationOut(BaseModel):
    id: uuid.UUID
    title: str
    department_id: uuid.UUID
    department_name: str
    soc_code: str | None


_SOC = re.compile(r"[0-9]{4}")


class DesignationIn(_Strict):
    title: Text120
    department_id: uuid.UUID
    soc_code: str | None = None

    _trim = field_validator("title", "soc_code", mode="before")(_clean)

    @field_validator("soc_code")
    @classmethod
    def _soc(cls, value: str | None) -> str | None:
        if value is not None and not _SOC.fullmatch(value):
            raise ValueError("A SOC code is 4 digits, such as 2231.")
        return value


class DesignationPatch(_Strict):
    title: Text120 | None = None
    department_id: uuid.UUID | None = None
    soc_code: str | None = None

    _trim = field_validator("title", "soc_code", mode="before")(_clean)

    @field_validator("soc_code")
    @classmethod
    def _soc(cls, value: str | None) -> str | None:
        if value is not None and not _SOC.fullmatch(value):
            raise ValueError("A SOC code is 4 digits, such as 2231.")
        return value
