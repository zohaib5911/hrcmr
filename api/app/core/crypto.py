"""Field-level encryption, blind indexes and masking (plan.md 4.5 and 4.1.7).

Sensitive values (NI number, passport number, bank details, visa references, TOTP secrets) are
encrypted with AES-256-GCM before they reach the database, so a stolen database or backup does not
expose them. This module is the only place that touches the keys.

Stored form: ``v1:<key id>:<base64url(nonce || ciphertext || tag)>``

* A fresh random 96-bit nonce per value, so the same plaintext never encrypts the same way twice.
* The key id says which key to use, so keys can be rotated: add ``k2``, make it the active key, run
  ``python -m app.cli rotate-keys``, then (once nothing uses ``k1``) remove it.
* Authenticated data (``context``, such as ``"users.mfa_secret"``) is bound into the tag, so a value
  copied into a different column or table fails to decrypt instead of being accepted.

A blind index (HMAC-SHA256) lets the database find equal values (for example a duplicate NI number)
without decrypting anything. It is one-way and keyed, so it is useless without ``BLIND_INDEX_KEY``.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

if TYPE_CHECKING:
    from collections.abc import Mapping

    from app.core.config import Settings

VERSION = "v1"
KEY_BYTES = 32  # AES-256
NONCE_BYTES = 12  # the 96 bits GCM is designed for
_MASK_CHARACTER = "•"


class CryptoConfigError(ValueError):
    """The key settings are unusable. The message names a variable, never a value."""


class DecryptionError(ValueError):
    """Not a valid ciphertext for this context and key. Says nothing more, on purpose."""


def _decode_key(encoded: object, *, variable: str) -> bytes:
    if not isinstance(encoded, str):
        raise CryptoConfigError(f"{variable} must hold base64 text")
    try:
        key = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise CryptoConfigError(f"{variable} must be base64") from exc
    if len(key) != KEY_BYTES:
        raise CryptoConfigError(f"{variable} must decode to exactly {KEY_BYTES} bytes")
    return key


@dataclass(frozen=True)
class KeyRing:
    """The encryption keys by id, which one encrypts new values, and the blind-index key."""

    keys: Mapping[str, bytes] = field(repr=False)
    active_kid: str
    blind_key: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if self.active_kid not in self.keys:
            raise CryptoConfigError(
                "FIELD_ENCRYPTION_ACTIVE_KID is not one of FIELD_ENCRYPTION_KEYS"
            )
        if ":" in "".join(self.keys):
            raise CryptoConfigError("FIELD_ENCRYPTION_KEYS ids must not contain ':'")

    @classmethod
    def from_settings(cls, settings: Settings) -> KeyRing:
        keys = settings.field_encryption_keys.get_secret_value()
        blind = settings.blind_index_key.get_secret_value()
        return cls.from_settings_values(
            keys_json=keys, active_kid=settings.field_encryption_active_kid, blind_index_key=blind
        )

    @classmethod
    def from_settings_values(
        cls, *, keys_json: str, active_kid: str, blind_index_key: str
    ) -> KeyRing:
        try:
            raw = json.loads(keys_json)
        except json.JSONDecodeError as exc:
            raise CryptoConfigError("FIELD_ENCRYPTION_KEYS must be JSON") from exc
        if not isinstance(raw, dict) or not raw:
            raise CryptoConfigError(
                'FIELD_ENCRYPTION_KEYS must be a JSON object like {"k1": "..."}'
            )
        keys = {
            str(kid): _decode_key(value, variable="FIELD_ENCRYPTION_KEYS")
            for kid, value in raw.items()
        }
        return cls(
            keys=keys,
            active_kid=active_kid,
            blind_key=_decode_key(blind_index_key, variable="BLIND_INDEX_KEY"),
        )


_override: KeyRing | None = None
_cached: KeyRing | None = None


def set_keyring(keyring: KeyRing | None) -> None:
    """Use this key ring instead of the one from the settings (tests, and the rotation command)."""
    global _override, _cached
    _override = keyring
    _cached = None


def current_keyring() -> KeyRing:
    """The key ring for this process: the override if one was set, else built from the settings."""
    global _cached
    if _override is not None:
        return _override
    if _cached is None:
        from app.core.config import get_settings

        _cached = KeyRing.from_settings(get_settings())
    return _cached


def _aad(context: str) -> bytes:
    return context.encode("utf-8")


def encrypt(plaintext: str, *, context: str, keyring: KeyRing | None = None) -> str:
    ring = keyring or current_keyring()
    nonce = os.urandom(NONCE_BYTES)
    sealed = AESGCM(ring.keys[ring.active_kid]).encrypt(
        nonce, plaintext.encode("utf-8"), _aad(context)
    )
    body = base64.urlsafe_b64encode(nonce + sealed).decode("ascii")
    return f"{VERSION}:{ring.active_kid}:{body}"


def key_id_of(token: str) -> str | None:
    """Which key encrypted this value, or None if it is not in our format."""
    parts = token.split(":", 2)
    return parts[1] if len(parts) == 3 and parts[0] == VERSION else None


def decrypt(token: str, *, context: str, keyring: KeyRing | None = None) -> str:
    ring = keyring or current_keyring()
    parts = token.split(":", 2)
    if len(parts) != 3 or parts[0] != VERSION or parts[1] not in ring.keys:
        raise DecryptionError("cannot decrypt value")
    try:
        raw = base64.urlsafe_b64decode(parts[2].encode("ascii"))
        nonce, sealed = raw[:NONCE_BYTES], raw[NONCE_BYTES:]
        plain = AESGCM(ring.keys[parts[1]]).decrypt(nonce, sealed, _aad(context))
        return plain.decode("utf-8")
    except (InvalidTag, binascii.Error, ValueError, UnicodeError) as exc:
        raise DecryptionError("cannot decrypt value") from exc


def needs_rotation(token: str, *, keyring: KeyRing | None = None) -> bool:
    """True when the value was not written with the active key."""
    ring = keyring or current_keyring()
    return key_id_of(token) != ring.active_kid


def reencrypt(token: str, *, context: str, keyring: KeyRing | None = None) -> str:
    """The same value, sealed again with the active key (and a new nonce)."""
    ring = keyring or current_keyring()
    return encrypt(decrypt(token, context=context, keyring=ring), context=context, keyring=ring)


# --- Blind index ------------------------------------------------------------------------------


def blind_index(value: str, *, purpose: str, scope: str, keyring: KeyRing | None = None) -> str:
    """A keyed hash of ``value`` for equality search, as 64 hex characters.

    ``purpose`` (for example ``"employee.ni_number"``) and ``scope`` (the company id) are mixed in,
    so the same NI number gives a different index in another column or another company, and a leaked
    index cannot be matched across customers. The caller normalises the value first (remove spaces,
    upper-case) so that "ab 12 34 56 c" and "AB123456C" are the same.
    """
    ring = keyring or current_keyring()
    message = b"\x00".join(part.encode("utf-8") for part in (purpose, scope, value))
    return hmac.new(ring.blind_key, message, hashlib.sha256).hexdigest()


# --- Masking ----------------------------------------------------------------------------------


def mask_tail(value: str, visible: int = 3) -> str:
    """Hide all but the last ``visible`` letters and digits, keeping spaces and dashes.

    ``mask_tail("AB 12 34 56 C")`` gives ``"•• •• •• 56 C"``. At most half of a value is ever shown,
    so a short secret is never mostly revealed.
    """
    positions = [i for i, ch in enumerate(value) if ch.isalnum()]
    visible = min(max(visible, 0), len(positions) // 2)
    hidden = set(positions[: len(positions) - visible])
    return "".join(_MASK_CHARACTER if i in hidden else ch for i, ch in enumerate(value))
