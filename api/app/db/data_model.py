"""``docs/data-model.md``, generated from the models so it cannot drift (plan.md section 6).

``python -m app.cli export-data-model --output ../docs/data-model.md`` writes it, and a test fails
when the committed file is not what the models produce.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Table
from sqlalchemy.dialects import postgresql

import app.db.registry  # noqa: F401  (registers every model on Base.metadata)
from app.db.base import Base

_POSTGRES = postgresql.dialect()  # type: ignore[no-untyped-call]


def _default(column_default: object) -> str:
    arg = getattr(column_default, "arg", None)
    return "" if arg is None else f"`{arg}`"


def _notes(table: Table, name: str) -> str:
    column = table.columns[name]
    notes: list[str] = []
    if column.primary_key:
        notes.append("primary key")
    notes += sorted(f"references `{fk.column.table.name}`" for fk in column.foreign_keys)
    if column.unique:
        notes.append("unique")
    return ", ".join(notes)


def _table_section(table: Table) -> list[str]:
    lines = [f"## `{table.name}`", ""]
    lines += ["| Column | Type | Null | Default | Notes |", "|---|---|---|---|---|"]
    for column in table.columns:
        type_sql = column.type.compile(dialect=_POSTGRES)
        null = "yes" if column.nullable else "no"
        default = _default(column.server_default)
        lines.append(
            f"| `{column.name}` | {type_sql} | {null} | {default} | {_notes(table, column.name)} |"
        )
    checks = sorted(str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint))
    if checks:
        lines += ["", "Checks:", ""] + [f"- `{check}`" for check in checks]
    lines.append("")
    return lines


def data_model_markdown() -> str:
    lines = [
        "# Data model",
        "",
        "Generated from the SQLAlchemy models by `python -m app.cli export-data-model`.",
        "Do not edit by hand: a test fails when this file is out of date.",
        "",
    ]
    for table in sorted(Base.metadata.tables.values(), key=lambda t: t.name):
        lines += _table_section(table)
    return "\n".join(lines).rstrip("\n") + "\n"
