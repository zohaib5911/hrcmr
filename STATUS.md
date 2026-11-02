# STATUS
Updated: 2026-11-02 18:50 (Europe/London)    Agent: Codex    Branch: dev    Commit: dfb5578
State: IN PROGRESS

## Last completed
- T6.5 — Employment tab: audited hire date, dated roles/history, responsibilities, previous employment, education, training and memberships

## Current task
- T6.6 — Salary
  - [x] Salary API, permission isolation and NMW tests (10 pass)
  - [ ] Hidden-until-shown salary UI and add-record sheet
  - [ ] Browser check and final validation
- Resume note: Salary API verified; next salary-section.tsx and add-record sheet in Employment. Previous: inspect pay model lookups; add compensation_router.py and schemas; fetch salary only on Show salary. Official rates source https://www.gov.uk/national-minimum-wage-rates verified 2026-11-02.

## Next tasks
- T6.6, T6.7, T6.8, Phase 6 gate

## Health
- CI on dev: red on ca40751 (generated data-model drift fixed in 889e1d8); all other jobs passed. CI on main: previously red; not reverified.
- Local checks run: affected API/reporting/doc 26 pass; employee web unit 13 pass; Employment browser journey + setup 2 pass; ruff/mypy/eslint/tsc and production build pass.

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
