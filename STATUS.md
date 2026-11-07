# STATUS
Updated: 2026-11-07 15:30 UTC    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: 2b81ea7

State: IN PROGRESS

## Last completed
- P13 — Phase 13 learning gate. PR #21 (dev -> main) merged, all 12 checks green. Full API suite 818 pass; web lint/typecheck/unit 786 pass; browser 429 pass; screenshots docs/screenshots/phase-13.
- T13.4 — certificates and public /verify (0fd8ff0). T13.3 — report, assign wizard, overdue job, My learning (6dac93f, 8c4d6f4). T13.2 — eight launch courses in api/seed/courses, unpublished pending owner review (1d560cb). T13.1 — course model, player, editor (e7c662a).
- P12 — Phase 12 org chart gate, PR #20 merged (16f8152).

## Current task
- T14.1 — Dashboard API, cards and setup checklist (micro_plan.md, tier S)
  - [ ] 1. GET /dashboard: one aggregated, permission-aware response (cards omitted without permission)
  - [ ] 2. GET /onboarding/checklist + dismiss
- Resume note: nothing written yet for T14.1. Read plan §8.2 (`grep -n '### 8.2' plan.md`) before starting.

## Next tasks
- T14.2 (S), T14.3 (S!). Then T14.4 is tier B: a SMALL model stops there with "BLOCKED — needs big model (T14.4)" and the BIG MODEL TASK message. T14.5, P14 and AUDIT-2 come after it.

## Health
- CI on dev: green (PR #21 checks all passed before merge). CI on main: green after PR #21.
- Local checks: T13.x — API full suite 818 pass; web lint, typecheck, unit 786 pass; browser e2e 429 pass.

## Issues / suggestions
- Eight launch courses (api/seed/courses) are unpublished; owner must review them. Nothing loads seed courses into production yet (owner decision: owner-role load or import through the editor).
- EHRC sources could not be verified (site returned 403 to the fetch), so the courses cite GOV.UK and Acas only.
- Certificate download and the public check: the verify page runs a sanity length check and returns the same generic answer for every unknown reference.
- Learning report is company-wide only; people managers with read_reports do not see their team's report yet (plan allows it; not built).
- Hierarchy levels: no UI to create or edit them yet (plan 8.13 wants an editable list); Change role sheet has no level picker.
- Test-order issue: some root-level test files mixed with tests/db/* give "fixture 'database' not found". Run them in separate pytest invocations; the default full run passes.
- Turnstile: production must set the site key (web) and secret (API) together.
- PR #16 (dependabot, python deps) is still open; not ours, left alone.

## Strategy / decisions taken
- Learning: courses are global with RLS (published only for learners); assignments are tenant-scoped; the table is course_assignments (plan 6.9), not micro_plan's learning_assignments.
- Certificates: public check uses a row policy keyed by a transaction setting (app.certificate_ref) so no other certificate is opened.
- The learning report requires company-wide scope (require() also admits own-scope holders, so the handler checks scope).
- RBAC guard: one reviewed public prefix added for /api/v1/public/certificates/ (tests/db/test_rbac_enforcement.py).
- Overdue job: company-local date; in-app notification only (no email).

## Owner actions needed
- Review the eight launch courses before publishing them (api/seed/courses). See PROGRESS.md.
- Decide how seed courses reach production.
- Phase 23: add a Cloudflare rate-limit rule for /careers/* (the API cannot tell visitors apart on server-rendered pages).
