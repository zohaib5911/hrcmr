"""Column types that do more than store a value."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.core.crypto import decrypt, encrypt

if TYPE_CHECKING:
    from sqlalchemy.engine import Dialect


class EncryptedString(TypeDecorator[str]):
    """Text that is AES-256-GCM encrypted on the way in and decrypted on the way out (plan 4.5).

    The database column is plain ``text`` holding ``v1:<key id>:<ciphertext>``. ``context`` names
    the column (``"users.mfa_secret"``) and is bound into the encryption, so a value cannot be
    copied into another column and accepted. It must stay the same for the life of the column.

    An encrypted column cannot be searched or sorted. For equality search add a second column
    holding ``blind_index(...)`` and query that.
    """

    impl = Text
    cache_ok = True

    def __init__(self, context: str) -> None:
        super().__init__()
        self.context = context

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        return None if value is None else encrypt(value, context=self.context)

    def process_result_value(self, value: str | None, dialect: Dialect) -> str | None:
        return None if value is None else decrypt(value, context=self.context)
