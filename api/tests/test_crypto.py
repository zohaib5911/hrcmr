"""The Done-when of T2.2: round trip, tamper detection and rotation (rotation of stored rows is in
tests/db/test_rotation.py)."""

from __future__ import annotations

import base64
import json
import os

import pytest

from app.core.crypto import (
    CryptoConfigError,
    DecryptionError,
    KeyRing,
    blind_index,
    decrypt,
    encrypt,
    key_id_of,
    mask_tail,
    needs_rotation,
    reencrypt,
)

CONTEXT = "users.mfa_secret"


def _key() -> str:
    return base64.b64encode(os.urandom(32)).decode()


def ring(*kids: str, active: str | None = None) -> KeyRing:
    return KeyRing.from_settings_values(
        keys_json=json.dumps({kid: _key() for kid in kids}),
        active_kid=active or kids[0],
        blind_index_key=_key(),
    )


@pytest.mark.parametrize("plain", ["AB123456C", "", "Zoë 日本語 🔒", "x" * 5000])
def test_a_value_round_trips(plain: str) -> None:
    keys = ring("k1")
    token = encrypt(plain, context=CONTEXT, keyring=keys)
    assert token.startswith("v1:k1:")
    assert plain not in token or plain == ""
    assert decrypt(token, context=CONTEXT, keyring=keys) == plain


def test_the_same_value_never_encrypts_the_same_way_twice() -> None:
    keys = ring("k1")
    assert encrypt("AB123456C", context=CONTEXT, keyring=keys) != encrypt(
        "AB123456C", context=CONTEXT, keyring=keys
    )


def _flip(token: str) -> str:
    head, _, body = token.rpartition(":")
    raw = bytearray(base64.urlsafe_b64decode(body))
    raw[-1] ^= 1  # inside the authentication tag
    return f"{head}:{base64.urlsafe_b64encode(bytes(raw)).decode()}"


def test_a_changed_value_is_refused() -> None:
    keys = ring("k1")
    token = encrypt("AB123456C", context=CONTEXT, keyring=keys)
    for bad in (
        _flip(token),
        token[:-4],
        "v1:k1:" + "A" * 10,
        "v2:k1:" + token.split(":", 2)[2],
        "k1:" + token.split(":", 2)[2],
        "plain text",
        "",
    ):
        with pytest.raises(DecryptionError):
            decrypt(bad, context=CONTEXT, keyring=keys)


def test_a_value_moved_to_another_column_is_refused() -> None:
    keys = ring("k1")
    token = encrypt("AB123456C", context="employees.ni_number", keyring=keys)
    with pytest.raises(DecryptionError):
        decrypt(token, context="employees.passport_number", keyring=keys)


def test_another_key_cannot_read_it() -> None:
    token = encrypt("AB123456C", context=CONTEXT, keyring=ring("k1"))
    with pytest.raises(DecryptionError):
        decrypt(token, context=CONTEXT, keyring=ring("k1"))  # same id, different key bytes
    with pytest.raises(DecryptionError):
        decrypt(token, context=CONTEXT, keyring=ring("k9"))  # unknown id


def test_rotation_moves_a_value_to_the_new_key_and_keeps_it_readable() -> None:
    old = ring("k1")
    token = encrypt("AB123456C", context=CONTEXT, keyring=old)
    both = KeyRing(
        keys={**old.keys, "k2": os.urandom(32)}, active_kid="k2", blind_key=old.blind_key
    )
    assert key_id_of(token) == "k1"
    assert needs_rotation(token, keyring=both)
    assert decrypt(token, context=CONTEXT, keyring=both) == "AB123456C"  # still readable meanwhile

    moved = reencrypt(token, context=CONTEXT, keyring=both)
    assert key_id_of(moved) == "k2"
    assert not needs_rotation(moved, keyring=both)
    assert moved != token

    only_new = KeyRing(keys={"k2": both.keys["k2"]}, active_kid="k2", blind_key=old.blind_key)
    assert decrypt(moved, context=CONTEXT, keyring=only_new) == "AB123456C"  # k1 can now be removed
    with pytest.raises(DecryptionError):
        decrypt(token, context=CONTEXT, keyring=only_new)


@pytest.mark.parametrize(
    ("keys_json", "active", "blind", "names"),
    [
        ("not json", "k1", None, "FIELD_ENCRYPTION_KEYS"),
        ("[]", "k1", None, "FIELD_ENCRYPTION_KEYS"),
        (json.dumps({"k1": "not base64!"}), "k1", None, "FIELD_ENCRYPTION_KEYS"),
        (json.dumps({"k1": base64.b64encode(b"short").decode()}), "k1", None, "32 bytes"),
        (None, "k2", None, "FIELD_ENCRYPTION_ACTIVE_KID"),
        (None, "k1", base64.b64encode(b"short").decode(), "BLIND_INDEX_KEY"),
        (json.dumps({"k:1": _key()}), "k:1", None, "':'"),
    ],
)
def test_unusable_key_settings_are_refused_by_name_and_never_echo_a_value(
    keys_json: str | None, active: str, blind: str | None, names: str
) -> None:
    secret = _key()
    with pytest.raises(CryptoConfigError, match=names) as raised:
        KeyRing.from_settings_values(
            keys_json=keys_json or json.dumps({"k1": secret}),
            active_kid=active,
            blind_index_key=blind or _key(),
        )
    assert secret not in str(raised.value)


def test_a_blind_index_is_stable_keyed_and_scoped() -> None:
    keys, other = ring("k1"), ring("k1")
    one = blind_index("AB123456C", purpose="employee.ni_number", scope="company-1", keyring=keys)
    assert one == blind_index(
        "AB123456C", purpose="employee.ni_number", scope="company-1", keyring=keys
    )
    assert len(one) == 64
    assert "AB123456C" not in one
    assert one != blind_index(
        "AB123456D", purpose="employee.ni_number", scope="company-1", keyring=keys
    )
    assert one != blind_index(
        "AB123456C", purpose="employee.ni_number", scope="company-2", keyring=keys
    )
    assert one != blind_index(
        "AB123456C", purpose="employee.passport", scope="company-1", keyring=keys
    )
    assert one != blind_index(
        "AB123456C", purpose="employee.ni_number", scope="company-1", keyring=other
    )


@pytest.mark.parametrize(
    ("plain", "visible", "masked"),
    [
        ("AB 12 34 56 C", 3, "•• •• •• 56 C"),
        ("12-34-56", 2, "••-••-56"),
        ("12345678", 4, "••••5678"),
        ("1234", 3, "••34"),  # at most half is ever shown
        ("7", 3, "•"),
        ("", 3, ""),
    ],
)
def test_masking_hides_all_but_the_tail(plain: str, visible: int, masked: str) -> None:
    assert mask_tail(plain, visible) == masked
