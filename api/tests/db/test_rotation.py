"""Key rotation against stored rows: `python -m app.cli rotate-keys` (T2.2)."""

from __future__ import annotations

import base64
import json
import os
from collections.abc import Iterator

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import NullPool

from app.core.crypto import DecryptionError, KeyRing, key_id_of, set_keyring
from app.db.rotate import encrypted_columns, rotate_keys
from app.modules.identity.models import User
from tests.db.support import DatabaseUnderTest, engine_for

K1, K2 = os.urandom(32), os.urandom(32)
BLIND = os.urandom(32)
SECRETS = {"a@example.com": "JBSWY3DPEHPK3PXP", "b@example.com": "KRSXG5CTMVRXEZLU"}


def _ring(keys: dict[str, bytes], active: str) -> KeyRing:
    return KeyRing(keys=keys, active_kid=active, blind_key=BLIND)


@pytest.fixture(autouse=True)
def _reset_keyring() -> Iterator[None]:
    yield
    set_keyring(None)


async def _insert(db: DatabaseUnderTest) -> None:
    engine = engine_for(db.owner_url, poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            await session.execute(text("truncate users cascade"))
            for email, secret in SECRETS.items():
                session.add(User(email=email, first_name="F", last_name="L", mfa_secret=secret))
            session.add(User(email="c@example.com", first_name="F", last_name="L"))  # no secret
            await session.commit()
    finally:
        await engine.dispose()


async def _stored(db: DatabaseUnderTest) -> dict[str, str | None]:
    engine = engine_for(db.owner_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(text("select email, mfa_secret from users"))
            return {row[0]: row[1] for row in rows.all()}
    finally:
        await engine.dispose()


async def _read(db: DatabaseUnderTest) -> dict[str, str | None]:
    engine = engine_for(db.owner_url, poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            users = (await session.execute(select(User))).scalars()
            return {str(user.email): user.mfa_secret for user in users}
    finally:
        await engine.dispose()


async def test_the_database_holds_only_ciphertext_and_the_orm_reads_plaintext(
    database: DatabaseUnderTest,
) -> None:
    set_keyring(_ring({"k1": K1}, "k1"))
    await _insert(database)
    stored = await _stored(database)
    assert stored["c@example.com"] is None
    for email, secret in SECRETS.items():
        sealed = stored[email]
        assert sealed is not None
        assert secret not in sealed
        assert key_id_of(sealed) == "k1"
    assert (await _read(database))["a@example.com"] == SECRETS["a@example.com"]


async def test_rotation_moves_every_row_to_the_new_key_and_can_be_repeated(
    database: DatabaseUnderTest,
) -> None:
    set_keyring(_ring({"k1": K1}, "k1"))
    await _insert(database)

    both = _ring({"k1": K1, "k2": K2}, "k2")
    set_keyring(both)
    engine = engine_for(database.owner_url, poolclass=NullPool)
    try:
        first = await rotate_keys(engine, both)
        second = await rotate_keys(engine, both)
    finally:
        await engine.dispose()
    assert first["users.mfa_secret"] == 2  # the two rows that have a secret
    assert second["users.mfa_secret"] == 0  # nothing left to do

    stored = await _stored(database)
    assert {key_id_of(v) for v in stored.values() if v} == {"k2"}

    # With the old key gone, everything still reads.
    set_keyring(_ring({"k2": K2}, "k2"))
    assert (await _read(database))["b@example.com"] == SECRETS["b@example.com"]
    # And with only the old key, nothing does: the rotation really changed the stored bytes.
    set_keyring(_ring({"k1": K1}, "k1"))
    with pytest.raises(DecryptionError):
        await _read(database)


def test_every_encrypted_column_is_found_by_its_type() -> None:
    assert [(t.name, c.name, ctx) for t, c, ctx in encrypted_columns()] == [
        ("company_bank_accounts", "sort_code", "company_bank_accounts.sort_code"),
        ("company_bank_accounts", "account_number", "company_bank_accounts.account_number"),
        ("employee_bank_details", "sort_code", "employee_bank_details.sort_code"),
        ("employee_bank_details", "account_number", "employee_bank_details.account_number"),
        ("employees", "ni_number", "employees.ni_number"),
        ("employees", "passport_number", "employees.passport_number"),
        ("rtw_checks", "share_code", "rtw_checks.share_code"),
        ("sponsor_documents", "reference_number", "sponsor_documents.reference_number"),
        ("sponsor_documents", "cos_number", "sponsor_documents.cos_number"),
        ("users", "mfa_secret", "users.mfa_secret"),
    ]


def test_deployed_settings_with_unusable_keys_refuse_to_start() -> None:
    from pydantic import SecretStr, ValidationError

    from app.core.config import AppEnv, Settings

    good = base64.b64encode(os.urandom(32)).decode()
    base: dict[str, object] = {
        "_env_file": None,
        "app_env": AppEnv.TEST,
        "domain": "example.test",
        "web_origin": "https://example.test",
        "admin_origin": "https://admin.example.test",
        "api_origin": "https://api.example.test",
        "database_url": SecretStr("postgresql+asyncpg://u@localhost/d"),
        "redis_url": SecretStr("redis://localhost:6379/0"),
        "session_secret": SecretStr("s" * 32),
        "field_encryption_keys": SecretStr(json.dumps({"k1": good})),
        "blind_index_key": SecretStr(good),
    }
    Settings(**base)  # type: ignore[arg-type]  # local and test environments are not checked
    broken = {**base, "field_encryption_keys": SecretStr("nope"), "app_env": AppEnv.STAGING}
    with pytest.raises(ValidationError):
        Settings(**broken)  # type: ignore[arg-type]
