"""Loads the ONS SOC 2020 coding index and unit-group descriptions (plan 6.10, T15.1).

Run from the api folder, with the owner connection string in DATABASE_URL_OWNER:

    cd api && uv run python ../data/import_soc.py

Each file lives in data/raw/ with a sidecar .json (source URL, bytes, SHA-256). A missing file is
downloaded from its sidecar's URL and checked. A file whose SHA-256 differs from its sidecar stops
the run, so a changed ONS file is never loaded without a decision. The first run also downloads the
local embedding model (about 70 MB, through fastembed). The connection string is never printed.
Re-running is safe: rows are updated in place, so no duplicates are added.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

if TYPE_CHECKING:
    from app.modules.soc.importer import ImportCounts

ROOT = Path(__file__).resolve().parent
API = ROOT.parent / "api"
RAW = ROOT / "raw"
# The release this run loads. A new ONS release means new files, a new sidecar and this line.
RELEASE = {
    "index": "soc2020-coding-index-2026-08-27",
    "units": "soc2020-unit-groups-2026-08-27",
}

# The app package lives in api/. Its modules are imported inside the functions below.
sys.path.insert(0, str(API))


def _say(line: str) -> None:
    sys.stdout.write(line + "\n")


def _fetch(url: str, target: Path) -> None:
    partial = target.with_name(target.name + ".part")
    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
        response.raise_for_status()
        with partial.open("wb") as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)
    partial.replace(target)


def _raw_file(stem: str) -> Path:
    from app.modules.soc.source import check_against_sidecar, sha256_of

    sidecar = RAW / f"{stem}.json"
    record = json.loads(sidecar.read_text(encoding="utf-8"))
    path = RAW / str(record["file"])
    if not path.exists():
        _say(f"downloading {path.name} ...")
        _fetch(record["source_url"], path)
        if sha256_of(path) != record["sha256"]:
            path.unlink()
            raise SystemExit(
                "Downloaded file does not match its sidecar; nothing loaded."
            )
    try:
        check_against_sidecar(path, sidecar)
    except ValueError as exc:
        raise SystemExit(
            f"Nothing loaded: {exc}. Keep the file or take a new release."
        ) from exc
    return path


async def _load(url: str, index_path: Path, units_path: Path) -> ImportCounts:
    from app.modules.soc.importer import fastembed_embedder, load_soc_source
    from app.modules.soc.source import load_source

    source = load_source(index_path, units_path)
    embed = fastembed_embedder()
    engine = create_async_engine(url, poolclass=NullPool, hide_parameters=True)
    try:
        async with AsyncSession(engine) as db:
            counts = await load_soc_source(db, source, embed)
            await db.commit()
    finally:
        await engine.dispose()
    return counts


def main() -> int:
    url = os.environ.get("DATABASE_URL_OWNER")
    if not url:
        raise SystemExit("DATABASE_URL_OWNER is not set. Nothing was loaded.")
    index_path = _raw_file(RELEASE["index"])
    units_path = _raw_file(RELEASE["units"])
    try:
        counts = asyncio.run(_load(url, index_path, units_path))
    except ValueError as exc:
        raise SystemExit(f"Nothing loaded: {exc}") from exc
    _say(
        f"unit groups: {counts.unit_groups} read, {counts.unit_groups_in_table} in table"
    )
    _say(
        f"index entries: {counts.index_entries} read, {counts.index_entries_in_table} in table"
    )
    _say(f"cross-references skipped (no code): {counts.cross_references_skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
