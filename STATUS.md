# STATUS
Updated: 2026-11-02 19:11 (Europe/London)    Agent: Codex    Branch: dev    Commit: d3efa8e
State: IN PROGRESS

## Last completed
- T6.8 — Related tab shells and live employee Activity feed

## Current task
- T6.8 — Leave, Attendance, Learning and Activity tabs
  - [x] Real Activity API with permission/isolation/pagination test
  - [x] Related tab shells linked to workspaces
  - [x] Browser journey and lint/types/build
- Resume note: Start Phase 6 gate. Review found deferred User Access employee-link picker still unbuilt (PROGRESS T5.2/T6.1), and header Add photo from plan 8.3 missing. Complete these integration requirements before full-suite/screenshot gate.

## Next tasks
- Phase 6 gate, Phase 7 (stop for audit after Phase 7)

## Health
- CI on dev: green 41504657493 (7c99e60); current Documents/Activity changes not yet in CI. CI on main: red (earlier audit-export fix on dev).
- Local checks run: T6.7 API/PDF/security 3 pass, browser/setup 2 pass; T6.8 Activity API 1 pass, browser/setup 2 pass; ruff/mypy/eslint/tsc, generated types and builds pass. No Phase 6 full-suite run yet.

## Issues / suggestions
- Deferred employee/user linking and Add photo must be completed before Phase 6 gate.
- Remove certifi exception after 2026-11-06; Dependabot #5 pending green CI.

## Strategy / decisions taken
- Leave/Attendance/Learning modules do not exist yet; named tab components are replacement points for Phases 8/9/13 and link to existing workspaces with employee_id/month. Activity already uses real audit data and includes owned-file events.
- PDF: plan-specified WeasyPrint, escaped template, no external resources, masked numbers, permission-gated salary, private/no-store, audited.
- Documents: existing scanned FileService, scoped employee/document associations, clean-only short-lived downloads.
- Roles append by effective date; hierarchy waits for Phase 9. Salary fetches only on Show salary.
- AI hidden without ANTHROPIC_API_KEY; Ask Mady deferred.

## Owner actions needed
- None blocking. Protect main and enable private vulnerability reporting.
