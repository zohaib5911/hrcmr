"""Rules about where code may live. They are cheap to check and expensive to get wrong."""

from __future__ import annotations

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
DB_PACKAGE = APP_DIR / "db"


def _python_files() -> list[Path]:
    return [
        path
        for path in sorted(APP_DIR.rglob("*.py"))
        if DB_PACKAGE not in path.parents and "tests" not in path.parts
    ]


def _raw_sql_uses(path: Path) -> list[str]:
    found: list[str] = []
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("sqlalchemy"):
            found += [
                f"{path.name}:{node.lineno} imports {a.name}"
                for a in node.names
                if a.name == "text"
            ]
        if isinstance(node, ast.Attribute) and node.attr in {"exec_driver_sql", "text"}:
            found.append(f"{path.name}:{node.lineno} uses .{node.attr}")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "text"
        ):
            found.append(f"{path.name}:{node.lineno} calls text()")
    return found


def test_raw_sql_lives_only_under_app_db() -> None:
    """plan.md 4.3: raw queries are forbidden outside db/. Everything else goes through the
    tenant-scoped session, which keeps Row-Level Security and query scoping in force."""
    violations = [use for path in _python_files() for use in _raw_sql_uses(path)]
    assert violations == []


def test_the_detector_would_catch_a_violation(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text("from sqlalchemy import text\nawait s.execute(text('select 1'))\n")
    assert _raw_sql_uses(bad)
    good = tmp_path / "good.py"
    good.write_text("from sqlalchemy import select\nawait s.execute(select(1))\n")
    assert _raw_sql_uses(good) == []
