"""Row-Level Security helpers (plan.md 4.3).

Isolation is enforced twice: the application scopes every query to the current company (see
``app/db/session.py``), and PostgreSQL itself refuses to show or change another company's rows.
This module is the database half.

How it works
------------
* Every transaction on a tenant session runs ``set_config('app.company_id', <id>, true)``.
* ``app_current_company_id()`` reads that setting. Unset or empty gives NULL, and
  ``company_id = NULL`` is never true, so a connection with no company sees NO tenant rows.
* Each tenant table has ``ENABLE ROW LEVEL SECURITY`` and a ``tenant_isolation`` policy for the
  ``app_user`` role, with identical ``USING`` and ``WITH CHECK`` clauses, so reads, updates,
  deletes and inserts are all confined to the current company.
* The table owner (``app_owner``) is not subject to the policy (no ``FORCE``). That keeps
  migrations and ``pg_dump`` backups working; the API never connects as the owner.

Views, materialised views and functions
---------------------------------------
A plain view runs with its OWNER's rights, and the owner is not subject to the policy, so a view
over a tenant table would show every company's rows to everyone. Views over tenant tables must be
created with ``security_invoker = true`` (use ``create_tenant_view``), which applies the CALLER's
policy. Materialised views cannot enforce Row-Level Security at all, and ``SECURITY DEFINER``
functions run as their owner, so both are reported by the drift guards below.

What this does not do: a caller that can run arbitrary SQL as ``app_user`` can change the setting.
RLS protects against missing filters and application bugs, not SQL injection. Parameterised
queries, and the rule that raw SQL lives only under ``app/db`` (enforced by a test), cover that.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sqlalchemy import text

from app.db.roles import APP_ROLE

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy.ext.asyncio import AsyncConnection

POLICY_NAME = "tenant_isolation"
TENANT_FUNCTION = "app_current_company_id"
UPDATED_AT_TRIGGER = "trg_set_updated_at"

_IDENTIFIER = re.compile(r"[a-z_][a-z0-9_]{0,62}")
_PRIVILEGES = {"SELECT", "INSERT", "UPDATE", "DELETE"}


def _ident(name: str) -> str:
    if not _IDENTIFIER.fullmatch(name):
        raise ValueError(f"unsafe SQL identifier: {name!r}")
    return f'"{name}"'


def _privileges(privileges: Iterable[str]) -> str:
    chosen = [p.upper() for p in privileges]
    if not chosen or not set(chosen) <= _PRIVILEGES:
        raise ValueError(f"privileges must be a non-empty subset of {sorted(_PRIVILEGES)}")
    return ", ".join(chosen)


def tenant_rls_statements(
    table: str,
    *,
    column: str = "company_id",
    privileges: Iterable[str] = ("SELECT", "INSERT", "UPDATE", "DELETE"),
) -> list[str]:
    """SQL that confines ``table`` to the current company and grants ``app_user`` access.

    ``column`` is ``company_id`` for tenant tables, and ``id`` for the companies table itself.
    Pass fewer ``privileges`` for tables the API must not fully control (for example, append-only).
    """
    t, c = _ident(table), _ident(column)
    check = f"{c} = {TENANT_FUNCTION}()"
    return [
        f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY",
        f"CREATE POLICY {POLICY_NAME} ON {t} AS PERMISSIVE FOR ALL TO {APP_ROLE} "
        f"USING ({check}) WITH CHECK ({check})",
        f"GRANT {_privileges(privileges)} ON {t} TO {APP_ROLE}",
    ]


def updated_at_trigger_statements(table: str) -> list[str]:
    return [
        f"CREATE TRIGGER {UPDATED_AT_TRIGGER} BEFORE UPDATE ON {_ident(table)} "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    ]


def enable_tenant_rls(table: str, **kwargs: object) -> None:
    """For use inside an Alembic migration's ``upgrade()``."""
    from alembic import op

    for statement in tenant_rls_statements(table, **kwargs):  # type: ignore[arg-type]
        op.execute(statement)


def add_updated_at_trigger(table: str) -> None:
    """For use inside an Alembic migration's ``upgrade()``."""
    from alembic import op

    for statement in updated_at_trigger_statements(table):
        op.execute(statement)


def create_tenant_view_statements(name: str, select_sql: str) -> list[str]:
    """A view that applies the CALLER's Row-Level Security (``security_invoker``), plus the grant.

    ``select_sql`` is trusted SQL written in a migration, never user input.
    """
    v = _ident(name)
    return [
        f"CREATE VIEW {v} WITH (security_invoker = true) AS {select_sql}",
        f"GRANT SELECT ON {v} TO {APP_ROLE}",
    ]


def create_tenant_view(name: str, select_sql: str) -> None:
    """For use inside an Alembic migration's ``upgrade()``."""
    from alembic import op

    for statement in create_tenant_view_statements(name, select_sql):
        op.execute(statement)


# --- Drift guards: used by the tests and by `python -m app.cli check-rls` after a deploy ---------

_MISSING_RLS = text(
    """
    select c.relname
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    join pg_attribute a on a.attrelid = c.oid and a.attname = 'company_id' and not a.attisdropped
    where n.nspname = 'public' and c.relkind in ('r', 'p')
      and (not c.relrowsecurity
           or not exists (select 1 from pg_policy p
                          where p.polrelid = c.oid and p.polname = :policy))
    order by c.relname
    """
)
_MISSING_TRIGGER = text(
    """
    select c.relname
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    join pg_attribute a on a.attrelid = c.oid and a.attname = 'updated_at' and not a.attisdropped
    where n.nspname = 'public' and c.relkind in ('r', 'p')
      and not exists (select 1 from pg_trigger t
                      where t.tgrelid = c.oid and t.tgname = :trigger and not t.tgisinternal)
    order by c.relname
    """
)


async def tables_missing_tenant_rls(
    connection: AsyncConnection, *, exempt: frozenset[str] = frozenset()
) -> list[str]:
    """Tables that have a ``company_id`` column but no RLS or no ``tenant_isolation`` policy."""
    rows = await connection.execute(_MISSING_RLS, {"policy": POLICY_NAME})
    return [name for (name,) in rows if name not in exempt]


async def tables_missing_updated_at_trigger(
    connection: AsyncConnection, *, exempt: frozenset[str] = frozenset()
) -> list[str]:
    """Tables with an ``updated_at`` column that nothing keeps current."""
    rows = await connection.execute(_MISSING_TRIGGER, {"trigger": UPDATED_AT_TRIGGER})
    return [name for (name,) in rows if name not in exempt]


_PLAIN_VIEWS = text(
    """
    select c.relname
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relkind = 'v'
      and not exists (select 1 from unnest(coalesce(c.reloptions, '{}')) as o
                      where o in ('security_invoker=true', 'security_invoker=on',
                                  'security_invoker=1'))
    order by c.relname
    """
)
_MATERIALIZED_VIEWS = text(
    """
    select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relkind = 'm' order by c.relname
    """
)
_SECURITY_DEFINER = text(
    """
    select p.proname
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.prosecdef
    order by p.proname
    """
)


async def views_bypassing_rls(
    connection: AsyncConnection, *, exempt: frozenset[str] = frozenset()
) -> list[str]:
    """Views that run as their owner and therefore show every company's rows."""
    return [name for (name,) in await connection.execute(_PLAIN_VIEWS) if name not in exempt]


async def materialized_views(
    connection: AsyncConnection, *, exempt: frozenset[str] = frozenset()
) -> list[str]:
    """Materialised views cannot enforce Row-Level Security."""
    return [name for (name,) in await connection.execute(_MATERIALIZED_VIEWS) if name not in exempt]


async def security_definer_functions(
    connection: AsyncConnection, *, exempt: frozenset[str] = frozenset()
) -> list[str]:
    """Functions that run with their owner's rights, bypassing the policy."""
    return [name for (name,) in await connection.execute(_SECURITY_DEFINER) if name not in exempt]
