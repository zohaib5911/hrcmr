"""foundations: extensions, UUID v7, tenant helper and updated_at trigger functions

Revision ID: 0001_foundations
Revises:
Create Date: 2026-11-01
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001_foundations"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Created by the provisioning step as a superuser (pgvector is not a "trusted" extension). This is
# a no-op when they exist, and makes a plain `alembic upgrade` work on an already-provisioned DB.
CREATE_EXTENSIONS = (
    "CREATE EXTENSION IF NOT EXISTS pgcrypto",
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",
    "CREATE EXTENSION IF NOT EXISTS unaccent",
    "CREATE EXTENSION IF NOT EXISTS vector",
    "CREATE EXTENSION IF NOT EXISTS citext",
)

# RFC 9562 UUID v7: 48-bit Unix milliseconds, then random bits. PostgreSQL 16 has no uuidv7().
UUID_V7 = """
CREATE FUNCTION uuid_generate_v7() RETURNS uuid
LANGUAGE plpgsql VOLATILE PARALLEL SAFE
SET search_path = pg_catalog, public
AS $$
DECLARE
    unix_ms bigint := (extract(epoch FROM clock_timestamp()) * 1000)::bigint;
    raw bytea := substring(int8send(unix_ms) FROM 3 FOR 6) || gen_random_bytes(10);
BEGIN
    raw := set_byte(raw, 6, (get_byte(raw, 6) & 15) | 112);  -- version 7
    raw := set_byte(raw, 8, (get_byte(raw, 8) & 63) | 128);  -- variant 10
    RETURN encode(raw, 'hex')::uuid;
END
$$
"""

# The company the current transaction is scoped to. Unset or empty gives NULL, so Row-Level Security
# policies that compare against it match nothing (fail closed) instead of raising an error.
CURRENT_COMPANY = """
CREATE FUNCTION app_current_company_id() RETURNS uuid
LANGUAGE sql STABLE PARALLEL SAFE
AS $$ SELECT NULLIF(current_setting('app.company_id', true), '')::uuid $$
"""

SET_UPDATED_AT = """
CREATE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END
$$
"""


def upgrade() -> None:
    for statement in CREATE_EXTENSIONS:
        op.execute(statement)
    op.execute(UUID_V7)
    op.execute(CURRENT_COMPANY)
    op.execute(SET_UPDATED_AT)


def downgrade() -> None:
    # Extensions are left in place: they are shared and were created by provisioning.
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
    op.execute("DROP FUNCTION IF EXISTS app_current_company_id()")
    op.execute("DROP FUNCTION IF EXISTS uuid_generate_v7()")
