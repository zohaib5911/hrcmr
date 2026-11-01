"""UUID version 7 (RFC 9562): a 48-bit Unix-millisecond timestamp followed by random bits.

Time-ordered primary keys keep b-tree indexes compact and make "newest first" cheap, while staying
unguessable (74 random bits). PostgreSQL 16 has no built-in generator, so the database has an
equivalent ``uuid_generate_v7()`` function (created by the first migration) for rows inserted
without going through Python.
"""

from __future__ import annotations

import secrets
import time
import uuid
from datetime import UTC, datetime


def uuid7() -> uuid.UUID:
    millis = time.time_ns() // 1_000_000
    raw = bytearray(millis.to_bytes(6, "big") + secrets.token_bytes(10))
    raw[6] = (raw[6] & 0x0F) | 0x70  # version 7
    raw[8] = (raw[8] & 0x3F) | 0x80  # RFC 4122 variant
    return uuid.UUID(bytes=bytes(raw))


def uuid7_datetime(value: uuid.UUID) -> datetime:
    """The creation time embedded in a version 7 UUID."""
    if value.version != 7:
        raise ValueError("not a version 7 UUID")
    return datetime.fromtimestamp(int.from_bytes(value.bytes[:6], "big") / 1000, tz=UTC)
