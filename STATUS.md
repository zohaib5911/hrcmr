# STATUS
Updated: 2026-11-02 20:14 (Europe/London)    Agent: Codex    Branch: dev    Commit: 24ea81b
State: HANDED OVER

## Last completed
- Phase 6 gate — PR #11 merged to main as 6acec98 after all 12 CI checks passed; clean dev synced

## Current task
- T7.1 — Right to Work checks
  - [x] Read plan T7.1, 6.4 and 8.4 requirements
  - [x] Employee/file baseline: ruff/mypy pass, employee integration 3 pass; source paths reviewed
  - [ ] RTW model/migration and derived-status view
  - [ ] API: four check types, history/correction, evidence selection/upload, evidence PDF; RBAC/isolation tests
  - [ ] Employee RTW tab and directory RTW pills/filters/deep links
  - [ ] Browser verification and final checks
- Resume note: T7.1 requirements/baseline ready; no RTW code written. Start api/app/modules/rtw/models.py and migration 0015 after api/alembic/versions/20261102_0014_emergency_relationships.py. Copy employee model/migration conventions, app/db/types.py EncryptedString, RecordMixin/TenantMixin and tenant RLS. Plan 6.4/8.4 define four check types, reasoned versioned correction, evidence and derived-status view; encrypted share code must never enter audit/PDF in full. Reuse employee scanned documents and record_pdf.py safeguards. Wire RTW profile tab and deferred employee-list RTW pills/filters/deep links. Candidate subject support must integrate with Phase 11 validation. Check main post-merge CI 41516923634 if it has finished; PR #11 checks already all passed.


## Next tasks
- T7.1, T7.2, T7.3, T7.4, T7.5, T7.6; Phase 7 gate then BLOCKED — audit requested

## Health
- CI on dev: green 41514098397 on 0878319; all 12 PR checks passed. CI on main: post-merge run 41516923634 pending; previous red audit-export fix is included.
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
