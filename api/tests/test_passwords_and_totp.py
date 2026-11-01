"""Passwords and authenticator codes (T2.3): argon2id settings, the password rules with the breach
service answering, failing and timing out, and RFC 6238's own test values."""

from __future__ import annotations

import base64
import hashlib

import httpx
import pytest

from app.core.totp import (
    generate_recovery_codes,
    generate_secret,
    hash_recovery_code,
    hotp,
    provisioning_uri,
    totp,
    verify_totp,
)
from app.modules.auth.passwords import (
    PasswordProblem,
    hash_password,
    is_breached,
    needs_rehash,
    password_problems,
    verify_password,
)

# --- passwords --------------------------------------------------------------------------------------


def test_hashes_are_argon2id_with_the_planned_cost_and_verify() -> None:
    hashed = hash_password("correct horse battery staple")
    assert hashed.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
    assert verify_password(hashed, "correct horse battery staple")
    assert not verify_password(hashed, "correct horse battery stapl3")
    assert not verify_password("not a hash", "anything")
    assert not needs_rehash(hashed)


def test_a_hash_made_with_weaker_settings_is_marked_for_replacement() -> None:
    from argon2 import PasswordHasher

    weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash("a password here")
    assert needs_rehash(weak)
    assert verify_password(weak, "a password here")


def _hibp(suffix_lines: str, status: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.pwnedpasswords.com"
        assert len(request.url.path.rsplit("/", 1)[1]) == 5  # only a 5-character prefix is sent
        assert request.headers["Add-Padding"] == "true"
        return httpx.Response(status, text=suffix_lines)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _suffix(password: str) -> str:
    return hashlib.sha1(password.encode(), usedforsecurity=False).hexdigest().upper()[5:]


async def test_a_password_in_a_known_breach_is_refused_and_padding_lines_are_ignored() -> None:
    password = "an-unusual-but-leaked-one-1"
    body = f"{_suffix(password)}:42\r\n0123456789ABCDEF0123456789ABCDEF012:0\r\n"
    assert await password_problems(password, client=_hibp(body)) == [PasswordProblem.BREACHED]
    padding_only = "0123456789ABCDEF0123456789ABCDEF012:0\r\n"
    assert await password_problems(password, client=_hibp(padding_only)) == []


async def test_if_the_breach_service_fails_the_local_list_still_applies() -> None:
    fine = "a perfectly fine passphrase 77"
    assert await is_breached(fine, _hibp("", status=503)) is None  # could not tell
    assert await password_problems(fine, client=_hibp("", status=503)) == []  # and does not block
    # A password on the common list is refused even when the service is down.
    assert await password_problems("passwordpassword", client=_hibp("", 503)) == [
        PasswordProblem.COMMON
    ]


async def test_a_slow_breach_service_does_not_hold_up_sign_up() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    assert await is_breached("some passphrase here 1", client) is None


async def test_length_rules() -> None:
    assert await password_problems("short", client=_hibp("")) == [PasswordProblem.TOO_SHORT]
    assert await password_problems("x" * 11, client=_hibp("")) == [PasswordProblem.TOO_SHORT]
    assert await password_problems("y" * 201, client=_hibp("")) == [PasswordProblem.TOO_LONG]


# --- RFC 6238 ---------------------------------------------------------------------------------------

# RFC 6238's published test key is the ASCII text "12345678901234567890". It is built here rather than
# written out, so the secret scanner has nothing to mistake for a real key.
RFC_SECRET = base64.b32encode(b"12345678901234567890").decode()


@pytest.mark.parametrize(
    ("at", "expected"),
    [
        (59, "287082"),
        (1111111109, "081804"),
        (1111111111, "050471"),
        (1234567890, "005924"),
        (2000000000, "279037"),
    ],
)
def test_codes_match_the_published_rfc_6238_values(at: int, expected: str) -> None:
    assert totp(RFC_SECRET, at=at) == expected


def test_hotp_matches_rfc_4226_values() -> None:
    assert [hotp(RFC_SECRET, n) for n in range(3)] == ["755224", "287082", "359152"]


def test_verification_allows_one_step_of_clock_drift_and_says_which_step_matched() -> None:
    at = 1111111109
    code = totp(RFC_SECRET, at=at)
    step = at // 30
    assert verify_totp(RFC_SECRET, code, at=at) == step
    assert verify_totp(RFC_SECRET, code, at=at + 30) == step  # a step late
    assert verify_totp(RFC_SECRET, code, at=at - 30) == step  # a step early
    assert verify_totp(RFC_SECRET, code, at=at + 90) is None
    for bad in ("", "12345", "1234567", "abcdef", "000000"):
        assert verify_totp(RFC_SECRET, bad, at=at) is None
    assert verify_totp(RFC_SECRET, f"{code[:3]} {code[3:]}", at=at) == step  # typed with a space


def test_secrets_and_uri() -> None:
    assert generate_secret() != generate_secret()
    assert len(generate_secret()) == 32
    uri = provisioning_uri("ABC234", "me@example.com", "Brand")
    assert uri.startswith("otpauth://totp/Brand%3Ame%40example.com?secret=ABC234&issuer=Brand")
    assert uri.endswith("&algorithm=SHA1&digits=6&period=30")


def test_recovery_codes_are_unique_readable_and_stored_only_as_keyed_hashes() -> None:
    codes = generate_recovery_codes()
    assert len(codes) == len(set(codes)) == 10
    assert all(len(code) == 11 and code[5] == "-" for code in codes)
    assert not set("".join(codes).replace("-", "")) & set("01ILO")  # nothing easily misread
    key = b"k" * 32
    stored = hash_recovery_code(codes[0], key)
    assert codes[0] not in stored
    assert len(stored) == 64
    assert stored == hash_recovery_code(codes[0].lower().replace("-", " "), key)  # typed loosely
    assert stored != hash_recovery_code(codes[0], b"j" * 32)
