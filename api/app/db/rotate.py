"""Re-encrypt every encrypted column with the active key (plan 4.1.7).

Run as ``python -m app.cli rotate-keys`` after adding a key to ``FIELD_ENCRYPTION_KEYS`` and making
it the active one. It finds the columns by their type (``EncryptedString``), so a new encrypted
column is included without anyone remembering to list it. It connects as the owner, because it must
reach every company's rows, and it changes only values written with a different key. It is safe to
run twice, and to stop and run again.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Column, Table, Text, literal, select, type_coerce, update

import app.db.registry  # noqa: F401  (registers every model on Base.metadata)
from app.core.crypto import KeyRing, current_keyring, needs_rotation, reencrypt
from app.db.base import Base
from app.db.types import EncryptedString

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

BATCH = 500


def encrypted_columns() -> list[tuple[Table, Column[str], str]]:
    """Every column in the schema that holds encrypted values, with its encryption context."""
    return [
        (table, column, column.type.context)
        for table in sorted(Base.metadata.tables.values(), key=lambda t: t.name)
        for column in table.columns
        if isinstance(column.type, EncryptedString)
    ]


async def rotate_keys(engine: AsyncEngine, keyring: KeyRing | None = None) -> dict[str, int]:
    """Re-encrypt values not written with the active key. Returns how many per ``table.column``."""
    ring = keyring or current_keyring()
    changed: dict[str, int] = {}
    for table, column, context in encrypted_columns():
        label = f"{table.name}.{column.name}"
        changed[label] = 0
        key = table.c.id
        # The column's own type would decrypt on the way out and encrypt on the way in; treating it
        # as plain text here lets this code see and write the stored ciphertext itself.
        raw = type_coerce(column, Text)
        last = None
        while True:
            query = select(key, raw).where(column.is_not(None)).order_by(key).limit(BATCH)
            if last is not None:
                query = query.where(key > last)
            async with engine.connect() as connection:
                rows = (await connection.execute(query)).all()
            if not rows:
                break
            async with engine.begin() as connection:
                for row_id, stored in rows:
                    if needs_rotation(stored, keyring=ring):
                        sealed = reencrypt(stored, context=context, keyring=ring)
                        await connection.execute(
                            update(table)
                            .where(key == row_id, raw == stored)
                            .values({column: literal(sealed, Text)})
                        )
                        changed[label] += 1
            last = rows[-1][0]
    return changed
