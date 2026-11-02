# STATUS
Updated: 2026-11-02 20:57 (Europe/London)    Agent: Codex    Branch: dev    Commit: 587787d
State: IN PROGRESS

## Last completed
- Phase 6 gate — PR #11 merged to main as 6acec98 after all 12 CI checks passed; clean dev synced

## Current task
- T7.1 — Right to Work checks
  - [x] Read plan T7.1, 6.4 and 8.4 requirements
  - [x] Employee/file baseline: ruff/mypy pass, employee integration 3 pass; source paths reviewed
  - [x] RTW model/migration 0015 and security-invoker status view (migration/doc checks 7 pass)
  - [x] API: four types, versioned/historical correction, scoped evidence and PDF; 12 RTW/PDF checks pass
  - [x] Employee RTW tab and directory RTW pills/filters/deep links
  - [x] Browser scenario prepared; TypeScript and affected ESLint pass
  - [ ] Browser verification and final checks
- Resume note: Production build and 15 employee/setup browser checks pass. RTW scenario stopped at axe call missing existing modal:true option (no app failure); fixed and rerun only rtw.spec.ts. UI implemented; browser scenario ready in web/tests/e2e/rtw.spec.ts, next run affected Playwright employees + rtw specs (UV_CACHE_DIR=/tmp/cmr-uv-cache); next verify T7.1 browser scenario for conditional forms, explicit saves, correction/history/PDF and evidence upload auto-selection, then finish checks. API/directory/PDF 15 pass, web list 6 pass, typecheck/lint pass. Core RTW API verified (12 RTW/PDF tests), migration/doc checks 7 pass. Next employee RTW tab and directory integration: status chips, conditional explicit-save forms, evidence picker/upload, correction and PDF actions; list status/pills/filters/deep links and summary counts. HR Admin records but cannot correct (rbac matrix); Company Admin correction only. Historical corrections stay historical; online corrections re-enter share code rather than reveal it. Candidate routes wait for Phase 11 validation.


## Next tasks
- T7.1, T7.2, T7.3, T7.4, T7.5, T7.6; Phase 7 gate then BLOCKED — audit requested

## Health
- CI on dev: green 41514098397 on 0878319; all 12 PR checks passed. CI on main: green 41516923634; previous red audit-export fix is included.
- Local/CI checks: API CI 422 pass; web 776 pass, guards 32 pass, full local Playwright 396 pass/144 screenshot-only skipped; final QA capture 5 pass/60 images. All lint/types/generated API/build/security/image checks green. Patched dependency local pip-audit clean, four PDF/file checks pass.

## Issues / suggestions
- Remove cooldown exceptions once safe: brotli after 2026-11-05, certifi after 2026-11-06, pypdf after 2026-11-12.
- Dependabot #5 pending green CI; avoid unrelated changes during T7.1.

## Strategy / decisions taken
- T7.1: IDSP records include explicit eligible document kind; status priority is not-recorded, failed/pending, expired, missing/unclean evidence, expiring (<=60 days), verified. Dates use company timezone. Share codes encrypted; no full code in responses/audit/PDF.
- Employee linking requires rbac.role.assign; changes self-service reach, unique per employee, audited. Full profile.write gates scanned photos; contact-only own writes cannot change photos.
- Hierarchy levels CRUD deferred to T12.1; other related tabs are shells for Phases 8/9/13. Activity already shows real employee/owned-file events.
- PDF: WeasyPrint, lazy native import, escaped template, blocked URL fetching, masked numbers and scoped salary. Direct-Jinja Semgrep annotation follows existing email renderer with escaping tests.
- Security patches brotli 1.2.1/pypdf 6.21.4 use narrow time-limited cooldown exceptions; no audit ignores.
- AI hidden without ANTHROPIC_API_KEY; Ask Mady deferred.

## Owner actions needed
- None blocking. Protect main and enable private vulnerability reporting.
