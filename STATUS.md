# STATUS
Updated: 2026-11-03 01:11    Agent: Codex    Branch: dev    Commit: ebed8eb
State: IN PROGRESS

## Last completed
- T7.1 — Right to Work checks, four forms, evidence, correction/history, derived status and PDFs

## Current task
- T7.2 — Sponsor documents and sponsored employees page
  - [x] Read T7.2/6.4/8.5 requirements and nearest modules; ruff/mypy/web types pass, T7.1 API baseline 15 pass
  - [x] Sponsor document model/migration 0016, encrypted references, versions and withdrawal/renewal; 7 migration/doc tests pass
  - [x] Scoped API, visa routes and sponsored employees query/tests; 14 sponsor integration tests pass
  - [ ] Employee document forms and sponsored employees table
  - [ ] Affected browser checks and final verification
- Resume note: Sponsor API ready: add/new version, renewal planning, withdrawal, clean evidence and sponsored-register routes; 14 integration tests pass; ruff/mypy/generated API/web types pass. Next employee sponsor document UI and sponsored-employees page. Reference/CoS fields stay masked and blank version fields preserve stored values. Sponsor PDF/CoC integration remains T7.6.


## Next tasks
- T7.2, T7.3, T7.4, T7.5, T7.6; Phase 7 gate then BLOCKED — audit requested

## Health
- CI on dev: green 41514098397 (Phase 6); T7.1 not yet run in CI. CI on main: green 41516923634.
- Local checks: T7.1 migration/doc 7, API/PDF/directory 15, list unit 6, employee/setup browser 15 and RTW/setup 2 pass. Ruff/mypy, web types/lint, generated API and production build pass. Phase 6 full gate passed before PR #11 merged.

## Issues / suggestions
- Remove cooldown exceptions once safe: brotli after 2026-11-05, certifi after 2026-11-06, pypdf after 2026-11-12.
- Dependabot #5 pending green CI; avoid unrelated changes.

## Strategy / decisions taken
- Sponsor metadata uses employee.rtw.read/write (own-read allowed, own-file uploads alone cannot change compliance metadata; auditors can read); register uses compliance.overview.read. Renewal target/notes never change expiry. Sponsor references/CoS masked, sponsored salary permission scoped.
- RTW priority: not recorded, failed/pending, expired, missing/unclean evidence, expiring (<=60 days), verified; dates use company timezone. Share codes never returned/exported in full. Historical corrections stay historical; Company Admin can correct, HR Admin can record only. Candidate validation/routes arrive in Phase 11.
- Browser file upload uses fixtures because e2e API has no storage config; real upload/scanning/binding/download tests use local services. Mobile checks wait for responsive cards after resize.
- Employee linking requires rbac.role.assign; hierarchy CRUD deferred to T12.1. PDF HTML escaped, external resources blocked, sensitive numbers masked, salary permission scoped.
- AI hidden without ANTHROPIC_API_KEY; Ask Mady deferred.

## Owner actions needed
- None blocking. Protect main and enable private vulnerability reporting.
