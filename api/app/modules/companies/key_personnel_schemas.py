"""What ``/key-personnel`` accepts and returns (plan.md 8.15)."""

from __future__ import annotations

import re
import uuid  # noqa: TC003  (pydantic resolves the annotations at runtime)
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Role = Literal["authorising_officer", "key_contact", "level1_user", "level2_user"]
Name = Annotated[str, Field(min_length=1, max_length=100)]
_PHONE = re.compile(r"[0-9 ()+\-]{6,25}")


def _clean(value: object) -> object:
    return value.strip() or None if isinstance(value, str) else value


def _phone(value: str | None) -> str | None:
    if value is not None and not _PHONE.fullmatch(value):
        raise ValueError("Enter a phone number using digits, spaces, + ( ) and -.")
    return value


class KeyPersonOut(BaseModel):
    id: uuid.UUID
    role: Role
    first_name: str
    last_name: str
    designation: str | None
    phone: str | None
    email: str | None
    same_as_authorising_officer: bool
    is_settled_or_british: bool | None
    has_proof_of_id: bool
    proof_of_id_name: str | None


class KeyPersonnel(BaseModel):
    people: list[KeyPersonOut]
    roles_filled: int = Field(description="How many of the 4 roles have someone in them.")


class KeyPersonIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Role
    # Left out when the person is the same as the Authorising Officer (their details are copied).
    first_name: Name | None = None
    last_name: Name | None = None
    designation: Annotated[str, Field(max_length=120)] | None = None
    phone: str | None = None
    email: EmailStr | None = None
    same_as_authorising_officer: bool = False
    is_settled_or_british: bool | None = None

    _trim = field_validator("first_name", "last_name", "designation", "phone", mode="before")(
        _clean
    )
    _check_phone = field_validator("phone")(_phone)


class KeyPersonPatch(BaseModel):
    """Only the fields that are sent change."""

    model_config = ConfigDict(extra="forbid")

    first_name: Name | None = None
    last_name: Name | None = None
    designation: Annotated[str, Field(max_length=120)] | None = None
    phone: str | None = None
    email: EmailStr | None = None
    same_as_authorising_officer: bool | None = None
    is_settled_or_british: bool | None = None

    _trim = field_validator("first_name", "last_name", "designation", "phone", mode="before")(
        _clean
    )
    _check_phone = field_validator("phone")(_phone)


class ProofLink(BaseModel):
    url: str
    expires_in: int
