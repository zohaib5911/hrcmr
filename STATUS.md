# STATUS
Updated: 2026-11-02 18:50 (Europe/London)    Agent: Codex    Branch: dev    Commit: dfb5578
State: IN PROGRESS

## Last completed
- T6.5 — Employment tab: audited hire date, dated roles/history, responsibilities, previous employment, education, training and memberships

## Current task
- T6.5 — Employment tab
  - [x] Requirements and baseline checks
  - [x] API and tenant/RBAC tests
  - [x] UI with explicit Save sheets
  - [x] Browser explicit-save journey and final checks
- Resume note: T6.5 complete. Start T6.6 salary in Employment tab. Check CI run 41502580515 (T6.4 baseline), then dispatch current dev once it finishes.

## Next tasks
- T6.6, T6.7, T6.8, Phase 6 gate

## Health
- CI on dev: red on ca40751 (generated data-model drift fixed in 889e1d8); e2e job still running. CI on main: previously red; not reverified.
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
