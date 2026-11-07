# STATUS
Updated: 2026-11-07 20:55 Europe/London    Agent: Claude Code (Opus 5.5, BIG)    Branch: dev    Commit: 5a7317e

State: IN PROGRESS

## Last completed
- T14.3 — live search in the command palette: GET /search (two characters or more, at most eight people and eight candidates, company-wide access only, tenant-scoped); People and Actions groups (736ab45).
- T14.2 — notifications: personal kinds reach every role; e-mail preferences immediate/daily/off; daily digest once per notice; policy e-mail only to immediate-mode people (3b72126).
- T14.1 — dashboard cards (company-wide only, so the employee role gets none), set-up checklist with per-person dismiss, /dashboard page (710c2f8).
- P13 — Phase 13 learning gate. PR #21 merged (all checks green); browser 429 pass; screenshots docs/screenshots/phase-13 (2b81ea7 is the last fix before the merge).
- T13.1–T13.4 — courses (eight launch courses in api/seed/courses, unpublished for owner review), player, assign wizard, report, overdue job, certificates and public /verify.
- P12 — Phase 12 org chart gate, PR #20 merged.

## Current task
- T14.4 — AI server layer (Ask Mady chat panel/tools deferred by owner)
  - [ ] 1 redaction + pseudonymisation layer (api/app/ai/redaction.py)
  - [ ] 2 Anthropic client (api/app/integrations/anthropic.py), gated on key + company toggle, rate limit 30/h/user
  - [ ] 3 ai_interactions metadata log (migration 0039)
  - [ ] 4 Phase 14 payload fuzz test
- Resume note: see journal.

## Next tasks
- T14.4 (B): Anthropic integration, redaction layer, tools, assistant panel. A big model does this and also writes the Phase 14 payload fuzz test.
- Then T14.5 (S): wire AI into letter drafting and reminder wording; P14 gate (S); AUDIT-2 stop (big model): covers T12.1 → P14.

## Health
- CI on dev: green (PR #21 checks all passed before merge). CI on main: green after PR #21. Latest dev commit 736ab45 has not gone through a PR yet (T14.x work is not gated yet).
- Local checks (T14.x): API DB groups pass (dashboard 4, notifications 4, search 4, RBAC 22+, learning 10, migrations 7, data-model doc); root-level tests 32 pass; web typecheck and lint pass; web unit 786 pass at Phase 13; browser specs dashboard 1 pass, shell 72 pass, shortcuts 7 pass.

## Issues / suggestions
- Eight launch courses (api/seed/courses) are unpublished; owner must review. Nothing loads seed courses into production yet (owner decision: owner-role load or import through the editor).
- EHRC sources could not be verified (site returned 403 to the fetch); the courses cite GOV.UK and Acas only.
- Dashboard: the "upload sponsor licence" checklist item from plan 8.2 is left out — there is no company-level sponsor-licence record in the codebase to check. Owner decision needed (add a record, or drop the item).
- Dashboard: the employee role's own cards are limited to "My learning"; "My leave balance" is not built (no leave-balance card in T14.1 steps). Error and empty states on /dashboard are code-level only, not browser-tested.
- Notifications: email digest is at 07:00 UTC for every company (plan gives no time). Only policy notices respect the "immediate" choice; other kinds have no immediate e-mail today.
- Learning report: people managers (read_reports) do not see their team's report yet.
- Hierarchy levels: no UI to create or edit them yet (plan 8.13 wants an editable list); Change role sheet has no level picker.
- Shell spec at 768 px had one intermittent axe finding (scrollable region on the employees page) that did not reproduce on rerun.
- Test-order issue: root-level test files mixed with tests/db/* give "fixture 'database' not found". Run them in separate pytest invocations; the default full run passes.
- Turnstile: production must set the site key (web) and secret (API) together.
- PR #16 (dependabot, python deps) is still open; not ours, left alone.

## Strategy / decisions taken
- Learning: courses are global with RLS (published only for learners); assignments are tenant-scoped; the table is course_assignments (plan 6.9), not micro_plan's learning_assignments.
- Certificates: the public check uses a row policy keyed by a transaction setting (app.certificate_ref) so no other certificate is opened.
- The learning report requires company-wide scope (require() also admits own-scope holders, so the handler checks scope).
- RBAC guard: reviewed public prefix /api/v1/public/certificates/ added in tests/db/test_rbac_enforcement.py.
- Dashboard: the page needs company.overview.read (every role holds it); the checklist needs company.profile.write (admin only). A dashboard card is included only when scope_for(role, permission) is company-wide.
- Notification kinds: PERSONAL_KINDS are always visible to the person; permission-gated kinds keep their gates.
- Search: people need company-wide employee.profile.read; candidates need company-wide recruitment.candidate.read; two characters minimum; eight per group.

## Owner actions needed
- Review the eight launch courses before publishing them (api/seed/courses). See PROGRESS.md.
- Decide how seed courses reach production.
- Decide on the sponsor-licence checklist item (plan 8.2).
- Phase 23: add a Cloudflare rate-limit rule for /careers/* (the API cannot tell visitors apart on server-rendered pages).
