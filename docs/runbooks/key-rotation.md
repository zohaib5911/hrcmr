# Rotating the field-encryption key

Sensitive fields (NI number, passport number, bank details, visa references, TOTP secrets) are
encrypted with AES-256-GCM. Each stored value starts with the id of the key that sealed it, for
example `v1:k1:...`. Rotation moves every value to a new key without downtime and without anyone
seeing a plaintext value. Do it when a key may have been exposed, when someone with access to it
leaves, and otherwise about once a year.

Never print or paste a key. Type values only into the Railway dashboard (or your local `.env` for
local work).

## Before you start

- Make sure a recent backup exists. Losing every copy of `FIELD_ENCRYPTION_KEYS` makes the
  encrypted fields unreadable for good.
- The keys live in one variable, `FIELD_ENCRYPTION_KEYS`, a JSON object of key id to key, and the id
  that seals new values is `FIELD_ENCRYPTION_ACTIVE_KID`.

## Steps

1. **Make a new key.** In your own terminal run `openssl rand -base64 32` and keep the output in your
   password manager. It must decode to exactly 32 bytes.
2. **Add it, still sealing with the old one.** In the Railway dashboard, change
   `FIELD_ENCRYPTION_KEYS` to include both, for example `{"k1":"<old>","k2":"<new>"}`, leave
   `FIELD_ENCRYPTION_ACTIVE_KID` as `k1`, and let the API redeploy. Every instance can now read
   values sealed with either key.
3. **Make the new key active.** Set `FIELD_ENCRYPTION_ACTIVE_KID` to `k2` and redeploy. New and
   edited values are sealed with `k2`; old ones are still readable.
4. **Re-encrypt what is stored.** Run `python -m app.cli rotate-keys` in the API service (needs
   `DATABASE_URL_OWNER`). It lists how many values it moved in each column. It is safe to stop and
   run again.
5. **Check.** Run it a second time: every column must say `0 re-encrypted`.
6. **Retire the old key.** Remove `k1` from `FIELD_ENCRYPTION_KEYS` and redeploy. Keep the old key
   in your password manager until the next backup that predates the rotation has expired, because
   an older backup still holds values sealed with it.

If the API refuses to start after a change, the message names the variable that is wrong (for
example `FIELD_ENCRYPTION_ACTIVE_KID is not one of FIELD_ENCRYPTION_KEYS`); fix it in the dashboard.

## The blind-index key

`BLIND_INDEX_KEY` makes the keyed hashes used to find duplicates (for example the same NI number
entered twice). It cannot be rotated by `rotate-keys`: a hash cannot be turned into a new hash
without the original value. Changing it means recomputing each index from the decrypted value, which
the module that owns that index must provide when it is built. Until then, do not change it.

## What the tests prove

`tests/test_crypto.py` and `tests/db/test_rotation.py` check that values round-trip, that any change
to a stored value (or moving it to another column) is refused, that rotation moves every row to the
new key and can be repeated, and that unusable key settings stop a deployed API from starting.
