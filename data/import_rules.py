"""Loads the GOV.UK Immigration Rules pages into a draft rules version (plan 6.10 and 8.17, T15.2).

Run from the api folder, with the owner connection string in DATABASE_URL_OWNER:

    cd api && uv run python ../data/import_rules.py            # import into a draft, print the diff
    cd api && uv run python ../data/import_rules.py --publish <version id>   # after review

The pages live in data/raw/rules/ with a sidecar .json (source URL, GOV.UK updated stamp, bytes,
SHA-256). A page whose SHA-256 differs from its sidecar stops the run. Importing never changes the
live version: it adds a draft and prints what differs from live. Publishing is a separate command,
run only once the owner has approved the draft. The connection string is never printed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parent
API = ROOT.parent / "api"
RULES = ROOT / "raw" / "rules"
# The release this run loads. A new GOV.UK update means new dated files, sidecars and this line.
RELEASE = "2026-10-29"

sys.path.insert(0, str(API))


def _say(line: str) -> None:
    sys.stdout.write(line + "\n")


def _models() -> None:
    """Every model, so foreign keys to other modules' tables (users) resolve."""
    import app.db.registry  # noqa: F401


def _pages() -> dict[str, tuple[Path, Path]]:
    from app.modules.soc_rules.source import PAGE_KINDS

    pages = {}
    for kind in PAGE_KINDS:
        html = RULES / f"appendix-{kind}-{RELEASE}.html"
        if not html.exists():
            raise SystemExit(
                f"Nothing loaded: {html.name} is missing from data/raw/rules."
            )
        pages[kind] = (html, html.with_suffix(".json"))
    return pages


def _print_diff(diff: dict[str, Any]) -> None:
    _say(
        "rows: "
        + ", ".join(f"{name} {count}" for name, count in diff["counts"].items())
    )
    if diff.get("against") is None:
        _say("no live version yet: this draft would be the first (v1)")
        return
    _say(
        f"compared with live version {diff['against']['name']} ({diff['against']['id']}):"
    )
    if not diff.get("has_changes"):
        _say("  no differences in rates, lists or salary rules")
        return
    for section, parts in diff["sections"].items():
        for kind in ("added", "removed"):
            if parts[kind]:
                _say(f"  {section} {kind}: {', '.join(parts[kind])}")
        for change in parts["changed"]:
            _say(
                f"  {section} {change['key']} {change['field']}: "
                f"{json.dumps(change['from'])} -> {json.dumps(change['to'])}"
            )


async def _import(url: str) -> None:
    from app.modules.soc_rules.importer import import_rules_source
    from app.modules.soc_rules.source import load_rules_source

    _models()
    source = load_rules_source(_pages())
    engine = create_async_engine(url, poolclass=NullPool, hide_parameters=True)
    try:
        async with AsyncSession(engine) as db:
            result = await import_rules_source(db, source)
            await db.commit()
    finally:
        await engine.dispose()
    if result.unchanged:
        _say("pages unchanged since the newest version: nothing added")
        return
    if result.replaced_draft:
        _say("an older unpublished draft was replaced")
    _say(f"draft rules version: {result.version_id}")
    _print_diff(result.diff_summary)
    _say("Review the diff, then publish with: --publish <version id>")


async def _publish(url: str, version_id: uuid.UUID) -> None:
    from app.modules.soc_rules.importer import publish_rules_version

    _models()
    engine = create_async_engine(url, poolclass=NullPool, hide_parameters=True)
    try:
        async with AsyncSession(engine) as db:
            await publish_rules_version(db, version_id)
            await db.commit()
    finally:
        await engine.dispose()
    _say(f"published rules version {version_id}; the previous live version is retired")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--publish", metavar="VERSION_ID", help="make this draft the live version"
    )
    args = parser.parse_args(argv)
    url = os.environ.get("DATABASE_URL_OWNER")
    if not url:
        raise SystemExit("DATABASE_URL_OWNER is not set. Nothing was loaded.")
    try:
        if args.publish:
            asyncio.run(_publish(url, uuid.UUID(args.publish)))
        else:
            asyncio.run(_import(url))
    except ValueError as exc:  # parse errors, a changed page, a publish refused
        raise SystemExit(f"Nothing changed: {exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
