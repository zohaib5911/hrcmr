"""Time-based one-time passwords (RFC 6238) and recovery codes (plan.md 4.2).

Written against the RFC rather than pulled in as a package: it is a few lines, and the tests check
it against the RFC's own published test values. SHA-1, 6 digits and a 30-second step are what every
authenticator app supports.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

DIGITS = 6
STEP_SECONDS = 30
SECRET_BYTES = 20  # 160 bits, the RFC's recommendation for SHA-1
RECOVERY_CODE_COUNT = 10
# No 0/O or 1/I/L: a code read off a printout must not be misread.
_RECOVERY_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_secret() -> str:
    return base64.b32encode(secrets.token_bytes(SECRET_BYTES)).decode("ascii").rstrip("=")


def _key(secret: str) -> bytes:
    return base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))


def hotp(secret: str, counter: int, digits: int = DIGITS) -> str:
    """RFC 4226."""
    digest = hmac.new(_key(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10**digits).zfill(digits)


def totp(
    secret: str, at: float | None = None, *, step: int = STEP_SECONDS, digits: int = DIGITS
) -> str:
    return hotp(secret, int((time.time() if at is None else at) // step), digits)


def verify_totp(
    secret: str, code: str, *, at: float | None = None, window: int = 1, step: int = STEP_SECONDS
) -> int | None:
    """The time step the code is valid for, or None. ``window`` allows for clocks a step apart.

    The caller must remember the returned step and refuse to accept it twice, so that a code seen
    over someone's shoulder cannot be replayed."""
    code = code.strip().replace(" ", "")
    if len(code) != DIGITS or not code.isdigit():
        return None
    now = int((time.time() if at is None else at) // step)
    matched: int | None = None
    for candidate in range(now - window, now + window + 1):  # no early exit: constant work
        if hmac.compare_digest(hotp(secret, candidate), code):
            matched = candidate
    return matched


def provisioning_uri(secret: str, account: str, issuer: str) -> str:
    """What the QR code holds: the app adds the account to its list from it."""
    label = quote(f"{issuer}:{account}", safe="")
    return (
        f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer, safe='')}"
        f"&algorithm=SHA1&digits={DIGITS}&period={STEP_SECONDS}"
    )


def generate_recovery_codes(count: int = RECOVERY_CODE_COUNT) -> list[str]:
    """Single-use codes like ``K7M2Q-9XWRB`` (50 bits each)."""
    codes = []
    for _ in range(count):
        raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(10))
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes


def normalise_recovery_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def hash_recovery_code(code: str, key: bytes) -> str:
    """Keyed hash, stored instead of the code. Fast is fine: each code is 50 random bits."""
    message = b"recovery:" + normalise_recovery_code(code).encode("ascii", "ignore")
    return hmac.new(key, message, hashlib.sha256).hexdigest()
