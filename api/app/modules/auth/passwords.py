"""Passwords (plan.md 4.2): argon2id hashing and the rules a new password must pass.

Hashing: argon2id with 64 MB of memory, 3 passes and 4 lanes. A hash made with older settings is
quietly replaced with a current one the next time its owner signs in (``needs_rehash``).

Rules: at least 12 characters; not on the NCSC list of commonly used passwords; and not in a known
breach. The breach check uses the Have I Been Pwned range service with k-anonymity: only the first 5
characters of the password's SHA-1 leave this server, never the password. If that service does not
answer within two seconds the local list alone decides, so sign-up never fails because of a third
party.
"""

from __future__ import annotations

import hashlib
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

import httpx
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.logging import get_logger

logger = get_logger("app.auth.passwords")

MIN_LENGTH = 12
# Argon2 reads the whole input; refusing absurd lengths keeps one request from costing much.
MAX_LENGTH = 200
HIBP_RANGE_URL = "https://api.pwnedpasswords.com/range/"
HIBP_TIMEOUT_SECONDS = 2.0
_COMMON_PASSWORDS = Path(__file__).parent / "data" / "common_passwords.txt"

_hasher = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=4)


class PasswordProblem(StrEnum):
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    COMMON = "common"
    BREACHED = "breached"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)


@lru_cache
def _dummy_hash() -> str:
    return hash_password("not-a-real-password-just-for-timing")


def spend_verification_time() -> None:
    """Do the work of checking a password that does not exist, so an unknown e-mail address takes as
    long to answer as a known one with the wrong password."""
    verify_password(_dummy_hash(), "a different password")


@lru_cache
def _common() -> frozenset[str]:
    return frozenset(_COMMON_PASSWORDS.read_text(encoding="utf-8").split())


def is_common(password: str) -> bool:
    return password.lower() in _common()


async def is_breached(password: str, client: httpx.AsyncClient | None = None) -> bool | None:
    """True if the password appears in a known breach, False if not, None if we could not tell."""
    digest = hashlib.sha1(password.encode("utf-8"), usedforsecurity=False).hexdigest().upper()
    prefix, suffix = digest[:5], digest[5:]
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=HIBP_TIMEOUT_SECONDS)
    try:
        response = await http.get(
            HIBP_RANGE_URL + prefix,
            headers={"Add-Padding": "true", "User-Agent": "hr-platform-password-check"},
            timeout=HIBP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.warning("hibp_unavailable")
        return None
    finally:
        if owns_client:
            await http.aclose()
    for line in response.content.decode("utf-8", "replace").splitlines():
        found, _, count = line.partition(":")
        if found.strip() == suffix and count.strip() not in ("", "0"):
            return True
    return False


async def password_problems(
    password: str, *, client: httpx.AsyncClient | None = None
) -> list[PasswordProblem]:
    """Everything wrong with a proposed password; an empty list means it is acceptable."""
    if len(password) < MIN_LENGTH:
        return [PasswordProblem.TOO_SHORT]
    if len(password) > MAX_LENGTH:
        return [PasswordProblem.TOO_LONG]
    if is_common(password):
        return [PasswordProblem.COMMON]
    if await is_breached(password, client):
        return [PasswordProblem.BREACHED]
    return []
