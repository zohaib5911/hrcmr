# STATUS
Updated: 2026-11-02 20:13 (Europe/London)    Agent: Codex    Branch: dev    Commit: 0878319
State: IN PROGRESS

## Last completed
- Phase 6 gate — PR #11 merged to main as 6acec98 after all 12 CI checks passed; clean dev synced

## Current task
- T7.1 — Right to Work checks
  - [x] Read plan T7.1, 6.4 and 8.4 requirements
  - [ ] Baseline checks and source review
  - [ ] RTW model/migration and derived-status view
  - [ ] API: four check types, history/correction, evidence selection/upload, evidence PDF; RBAC/isolation tests
  - [ ] Employee RTW tab and directory RTW pills/filters/deep links
  - [ ] Browser verification and final checks
- Resume note: No RTW code exists yet. Next inspect api/app/db models/migration conventions and encrypted field types; add api/app/modules/rtw with a migration after 0014. Reuse scanned employee document APIs and record_pdf.py rendering safeguards. Requirements: encrypted 9-character share code; conditional IDSP/manual-list fields; dated checks/checker/outcome/evidence; immutable history and reasoned correction; derived statuses including evidence_missing and expiring <=60 days. Candidate records arrive in Phase 11, so record how their validation will be integrated. Baseline CI is green on 0878319.

## Next tasks
- T7.1, T7.2, T7.3, T7.4, T7.5, T7.6; Phase 7 gate then BLOCKED — audit requested

## Health
- CI on dev: green 41514098397 on 0878319; all 12 PR checks passed. CI on main: new post-merge run pending; previous red audit-export fix is included.
- Local/CI checks: API CI 422 pass; web 776 pass, guards 32 pass, full local Playwright 396 pass/144 screenshot-only skipped; final QA capture 5 pass/60 images. All lint/types/generated API/build/security/image checks green. Patched dependency local pip-audit clean, four PDF/file checks pass.

## Issues / suggestions
- Remove cooldown exceptions once safe: brotli after 2026-11-05, certifi after 2026-11-06, pypdf after 2026-11-12.
- Dependabot #5 pending green CI; avoid unrelated changes during T7.1.

## Strategy / decisions taken
- Employee linking requires rbac.role.assign; changes self-service reach, unique per employee, audited. Full profile.write gates scanned photos; contact-only own writes cannot change photos.
- Hierarchy levels CRUD deferred to T12.1; other related tabs are shells for Phases 8/9/13. Activity already shows real employee/owned-file events.
- PDF: WeasyPrint, lazy native import, escaped template, blocked URL fetching, masked numbers and scoped salary. Direct-Jinja Semgrep annotation follows existing email renderer with escaping tests.
- Security patches brotli 1.2.1/pypdf 6.21.4 use narrow time-limited cooldown exceptions; no audit ignores.
- AI hidden without ANTHROPIC_API_KEY; Ask Mady deferred.

## Owner actions needed
- None blocking. Protect main and enable private vulnerability reporting.
