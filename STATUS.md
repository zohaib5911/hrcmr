# STATUS
Updated: 2026-11-02 19:11 (Europe/London)    Agent: Codex    Branch: dev    Commit: d3efa8e
State: IN PROGRESS

## Last completed
- T6.8 — Related tab shells and live employee Activity feed

## Current task
- Phase 6 gate
  - [x] Deferred User Access employee linking API/UI; API and browser tests pass
  - [x] Profile photo API/UI; real scanned upload/read and browser tests pass
  - [ ] Full suite: API 421 passed, 1 shared-schema fixture failure fixed; affected RBAC/User Access 26 pass; web 776 + guards 32 pass; full browser next
  - [ ] Design QA screenshots at 390/1280; phase summary
  - [ ] PR dev to main; merge only on green CI
- Resume note: web gate clean (776 unit, 32 guards, lint/types/generated API); next full Playwright once then SCREENSHOTS=1 Phase 6 capture. Previous: API gate done; fixture fix verified by 26 affected tests. Next full web, guards and Playwright. Previous: integration gaps verified. Run full API, web/guards, then full Playwright once, sequentially. Screenshot spec phase6-screenshots.spec.ts ready (SCREENSHOTS=1). Previous: run Deferred employee linking Playwright test; then full suite and screenshots. Previous: finish integration gaps identified in PROGRESS/plan 8.3 before gate checks. Link/unlink must use tenant-safe employee validation, prevent duplicate links and audit changes.

## Next tasks
- Phase 6 gate, Phase 7 (stop for audit after Phase 7)

## Health
- CI on dev: green 41504657493 (7c99e60); current Documents/Activity changes not yet in CI. CI on main: red (earlier audit-export fix on dev).
- Local checks run: T6.7 API/PDF/security 3 pass, browser/setup 2 pass; T6.8 Activity API 1 pass, browser/setup 2 pass; ruff/mypy/eslint/tsc, generated types and builds pass. No Phase 6 full-suite run yet.

## Issues / suggestions
- Deferred employee/user linking and Add photo must be completed before Phase 6 gate.
- Remove certifi exception after 2026-11-06; Dependabot #5 pending green CI.

## Strategy / decisions taken
- Employee links require rbac.role.assign (Company Admin), since changing a link changes self-service record reach. Admin may link their own account. Photos require full employee.profile.write, excluding contact-only write_own.
- Leave/Attendance/Learning modules do not exist yet; named tab components are replacement points for Phases 8/9/13 and link to existing workspaces with employee_id/month. Activity already uses real audit data and includes owned-file events.
- PDF: plan-specified WeasyPrint, escaped template, no external resources, masked numbers, permission-gated salary, private/no-store, audited.
- Documents: existing scanned FileService, scoped employee/document associations, clean-only short-lived downloads.
- Roles append by effective date; hierarchy waits for Phase 9. Salary fetches only on Show salary.
- AI hidden without ANTHROPIC_API_KEY; Ask Mady deferred.

## Owner actions needed
- None blocking. Protect main and enable private vulnerability reporting.
