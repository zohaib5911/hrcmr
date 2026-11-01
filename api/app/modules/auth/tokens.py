"""Opaque random tokens: session cookies, invitation links, e-mailed codes.

A token is 256 random bits. Only its SHA-256 hash is ever stored, so a database or backup leak does
not hand anyone a working session or link. SHA-256 (not a slow hash) is right here because the input
is already unguessable; slow hashing is for passwords, which people choose.
"""

from __future__ import annotations

import hashlib
import secrets

TOKEN_BYTES = 32


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
