# STATUS
Updated: 2026-11-03 01:23    Agent: Codex    Branch: dev    Commit: 8c93bc6
State: IN PROGRESS

## Last completed
- T7.2 — Sponsor document model/API/forms/history, renewal/withdrawal and sponsored employees register

## Current task
- T7.3 — Working-day calculator, change of circumstances and organisation changes
  - [x] Requirements and GOV.UK Part 3/glossary/calendar checked 2026-11-03; holiday baseline 6 tests, ruff/mypy pass
  - [ ] Working-day calculator with GOV.UK bank-holiday examples
  - [ ] Change/org-change models, migration and immutable snapshots
  - [ ] Scoped APIs, deadlines and mark-reported tests
  - [ ] Employee change form/log and company-wide pages
  - [ ] Affected browser checks and final verification
- Resume note: T7.3 sources verified and holiday baseline checked. Next pure working-day calculator + unit examples from official bank-holiday dates, then changes/org-change models/migration/API. Use Monday-Friday excluding regional bank holidays; start counting after event date. Part 3 C2.3 excludes AO/Key Contact replacements from normal 20 days, so represent that exception as prompt reporting rather than invent a fixed legal deadline. No T7.3 code yet.


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
