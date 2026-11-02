# STATUS
Updated: 2026-11-02 21:03 (Europe/London)    Agent: Codex    Branch: dev    Commit: 4baaf65
State: IN PROGRESS

## Last completed
- T7.1 — Right to Work checks, four forms, evidence, correction/history, derived status and PDFs

## Current task
- T7.2 — Sponsor documents and sponsored employees page
  - [x] Read T7.2/6.4/8.5 requirements and nearest modules; ruff/mypy/web types pass, T7.1 API baseline 15 pass
  - [ ] Sponsor document model/migration, encrypted references, versions and withdrawal/renewal
  - [ ] Scoped API, visa routes and sponsored employees query/tests
  - [ ] Employee document forms and sponsored employees table
  - [ ] Affected browser checks and final verification
- Resume note: T7.1 complete. Next T7.2 model/API/UI in plan order; read relevant sections and copy employees/RTW patterns. Sponsor Compliance tab/PDF itself is T7.6; T7.2 needs document management reachable to use now. No T7.2 code yet. Use document.file.read/write plus employee reach; sponsored register requires compliance.overview.read. Renewal records target date/notes, does not change expiry or imply renewed. References encrypted and masked; updates preserve stored reference/CoS if fields left blank.

## Next tasks
- T7.2, T7.3, T7.4, T7.5, T7.6; Phase 7 gate then BLOCKED — audit requested

## Health
- CI on dev: green 41514098397 (Phase 6); T7.1 not yet run in CI. CI on main: green 41516923634.
- Local checks: T7.1 migration/doc 7, API/PDF/directory 15, list unit 6, employee/setup browser 15 and RTW/setup 2 pass. Ruff/mypy, web types/lint, generated API and production build pass. Phase 6 full gate passed before PR #11 merged.

## Issues / suggestions
- Remove cooldown exceptions once safe: brotli after 2026-11-05, certifi after 2026-11-06, pypdf after 2026-11-12.
- Dependabot #5 pending green CI; avoid unrelated changes.

## Strategy / decisions taken
- RTW priority: not recorded, failed/pending, expired, missing/unclean evidence, expiring (<=60 days), verified; dates use company timezone. Share codes never returned/exported in full. Historical corrections stay historical; Company Admin can correct, HR Admin can record only. Candidate validation/routes arrive in Phase 11.
- Browser file upload uses fixtures because e2e API has no storage config; real upload/scanning/binding/download tests use local services. Mobile checks wait for responsive cards after resize.
- Employee linking requires rbac.role.assign; hierarchy CRUD deferred to T12.1. PDF HTML escaped, external resources blocked, sensitive numbers masked, salary permission scoped.
- AI hidden without ANTHROPIC_API_KEY; Ask Mady deferred.

## Owner actions needed
- None blocking. Protect main and enable private vulnerability reporting.
