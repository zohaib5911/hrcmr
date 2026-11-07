# STATUS
Updated: 2026-11-08 Europe/London    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: (see git log)
State: IN PROGRESS

## Last completed
- AUDIT-2 round 2 — PASS (0 P0 / 0 P1 / 0 P2). Tag audit-pass-2.

## Current task
- T15.1 — ONS SOC data import and local embeddings (S!)
  - [ ] step 0: find and record ONS download URLs (Watch line; BLOCKED if not found)
  - [ ] step 1: add fastembed + pgvector; migration for soc_unit_groups, soc_index_entries (vector + trigram)
  - [ ] step 2: data/import_soc.py (raw files in data/raw/ with SHA-256 + source-URL sidecar .json; load; embeddings)
  - [ ] step 3: fixture (~50 rows) under api/tests/fixtures/soc/; tests never download
  - [ ] done when: re-runnable import (no duplicates); fixture import test passes; row counts in PROGRESS
- Resume note: start at step 0. Check ONS URLs with WebSearch/WebFetch, then the migration. Run api ruff, mypy and the new tests only.

## Next tasks
- T15.2 (B), T15.3 (B), T15.4 (S!), T15.5 (S!)

## Health
- CI on dev: last PR run green (#22)    CI on main: green
- Local checks run: none yet for T15.1

## Issues / suggestions
- Push target: AGENTS.md says work on dev (main is protected). Pushing to origin/dev.

## Strategy / decisions taken
- none yet

## Owner actions needed
- none for T15.1 unless the ONS URLs are not found (then BLOCKED)
