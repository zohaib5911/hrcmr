# STATUS
Updated: 2026-11-02 19:02 (Europe/London)    Agent: Codex    Branch: dev    Commit: f7199b9
State: IN PROGRESS

## Last completed
- T6.6 — Hidden salary, compensation history, explicit add record and age-band minimum-wage preview

## Current task
- T6.6 — Salary
  - [x] Salary API and minimum-wage tests (10 pass)
  - [x] Hidden salary UI and add-record sheet
  - [x] Browser journey (2 pass including setup), lint/types/build
- Resume note: T6.6 complete. Next T6.7 Documents and employee PDF. CI 41504657493 runs 7c99e60; check results before proceeding if red.

## Next tasks
- T6.7, T6.8, Phase 6 gate

## Health
- CI on dev: run 41504657493 pending on 7c99e60; previous generated-doc drift fixed. CI on main: previously red; not reverified.
- Local checks run: salary API/unit 10 pass and browser/setup 2 pass; salary lint/types/build clean. Earlier: affected API/reporting/doc 26 pass; employee web unit 13 pass; Employment browser journey + setup 2 pass; ruff/mypy/eslint/tsc and production build pass.

## Issues / suggestions
- Remove certifi exception after 2026-11-06; Dependabot #5 pending green CI.

## Strategy / decisions taken
- Roles append in increasing effective-date order; ended_at is exclusive. List, summary and reporting access use today's effective role, including scheduled changes.
- Org assignment write permission gates Employment edits; profile read scope gates views. Role names are supplied for readers without company settings permissions.
- Hierarchy level selection waits for the Phase 9 organogram table; arbitrary IDs refused meanwhile.
- Employees may edit own Personal details, not identity/bank. Reveal needs step-up and is audited.
- Relay mode; AI features hidden without ANTHROPIC_API_KEY; Ask Mady deferred.

## Owner actions needed
- None blocking. Protect main and enable private vulnerability reporting.
