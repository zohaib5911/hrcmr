# STATUS
Updated: 2026-11-08 Europe/London    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: e48eff0
State: IN PROGRESS

## Last completed
- T15.3 — Rules engine (engine.py, loader.py), 27 golden tests + 1 DB test.
- T15.2 — Rules-data importer: GOV.UK pages to draft rules version with diff; publish sets live + RQF levels.

## Current task
- T15.4 — Search and match API (S!)
  - [ ] step 1: GET /soc/search?q= (trigram + full-text + vector, top 10)
  - [ ] step 2: POST /soc/match: retrieval -> Claude re-rank (JSON schema) -> rules engine on top 3; without AI: retrieval order, confidence null, "not AI-ranked" flag
  - [ ] done when: works with and without key (AI client mocked); confidence < 60 flagged low_confidence
- Resume note: start by reading api/app/modules/soc, api/app/integrations/anthropic.py, api/app/modules/soc_rules/loader.py + engine.py public API, and an existing router (letters) for the pattern.

## Next tasks
- T15.5 (S!), T15.6 (S)

## Health
- CI on dev: not run since T15.1 (Phase 15 gate PR runs it)    CI on main: green (last PR #22)
- Local checks run: none yet this session

## Issues / suggestions
- Test harness: temporary_database() sets cluster-wide roles app_owner/app_user per run; do not run DB suites in parallel.

## Strategy / decisions taken
- (T15.4) to be recorded during work.

## Owner actions needed
- Load SOC tables: `cd api && DATABASE_URL_OWNER=<owner connection string> uv run python ../data/import_soc.py` (set the variable in your shell; never paste it in chat).
- Publish rules v1 via data/import_rules.py (see handover notes in git history).
