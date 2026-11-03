# STATUS
Updated: 2026-11-03 01:36    Agent: Codex    Branch: dev    Commit: 1bfced2
State: IN PROGRESS

## Last completed
- T7.2 — Sponsor document model/API/forms/history, renewal/withdrawal and sponsored employees register

## Current task
- T7.3 — Working-day calculator, change of circumstances and organisation changes
  - [x] Requirements and GOV.UK Part 3/glossary/calendar checked 2026-11-03; holiday baseline 6 tests, ruff/mypy pass
  - [x] Working-day calculator with GOV.UK bank-holiday examples; 12 unit checks pass
  - [x] Change/org-change models and migration 0017; immutable worker/reported records, unreported org CRUD; 7 migration/doc checks pass
  - [x] Scoped APIs, deadlines and mark-reported tests; 7 integration + 12 working-day checks pass
  - [ ] Employee change form/log and company-wide pages
  - [ ] Affected browser checks and final verification
- Resume note: T7.3 API verified: 7 integration + 12 pure working-day tests, migration/doc 7; ruff/mypy/generated API/web types pass. Next employee change form/log, company-wide CoC/org pages and browser scenario. E2E API currently has an empty bank-holiday table: seed official fixed test dates in tests/e2e_server.py (test-only) before exercising real deadline API; runtime still uses weekly GOV.UK import, never fetch on requests. Snapshot and company-timezone reporting tested; no UI yet.


## Next tasks
- T7.3, T7.4, T7.5, T7.6; Phase 7 gate then BLOCKED — audit requested

## Health
- CI on dev: green 41514098397 (Phase 6); T7.1 not yet run in CI. CI on main: green 41516923634.
- Local checks: T7.2 migration/doc 7, sponsor API 14, sponsor/setup browser 2 and adjacent RTW/setup 2 pass; lint/types/generated API/build pass. Previous  T7.1 migration/doc 7, API/PDF/directory 15, list unit 6, employee/setup browser 15 and RTW/setup 2 pass. Ruff/mypy, web types/lint, generated API and production build pass. Phase 6 full gate passed before PR #11 merged.

## Issues / suggestions
- Remove cooldown exceptions once safe: brotli after 2026-11-05, certifi after 2026-11-06, pypdf after 2026-11-12.
- Dependabot #5 pending green CI; avoid unrelated changes.

## Strategy / decisions taken
- T7.3 verified sources: GOV.UK sponsor Part 3 (C1.13/C2.3), glossary and bank-holidays page, checked 2026-11-03. AO/Key Contact replacements get prompt-report status, other org changes standard 20 working days. Regional calendar data must cover the requested dates; do not silently ignore missing bank holidays.
- T7.2 exposes the document section of Sponsor compliance now so the feature is usable; T7.6 adds its PDF/CoC integration and notifications.
- Sponsor metadata uses employee.rtw.read/write (own-read allowed, own-file uploads alone cannot change compliance metadata; auditors can read); register uses compliance.overview.read. Renewal target/notes never change expiry. Sponsor references/CoS masked, sponsored salary permission scoped.
- RTW priority: not recorded, failed/pending, expired, missing/unclean evidence, expiring (<=60 days), verified; dates use company timezone. Share codes never returned/exported in full. Historical corrections stay historical; Company Admin can correct, HR Admin can record only. Candidate validation/routes arrive in Phase 11.
- Browser file upload uses fixtures because e2e API has no storage config; real upload/scanning/binding/download tests use local services. Mobile checks wait for responsive cards after resize.
- Employee linking requires rbac.role.assign; hierarchy CRUD deferred to T12.1. PDF HTML escaped, external resources blocked, sensitive numbers masked, salary permission scoped.
- AI hidden without ANTHROPIC_API_KEY; Ask Mady deferred.

## Owner actions needed
- None blocking. Protect main and enable private vulnerability reporting.
