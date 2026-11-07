# STATUS
Updated: 2026-11-07 06:20 UTC (Europe/London 06:20)    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: 16f8152

State: IN PROGRESS

## Last completed
- P12 — Phase 12 org chart gate. PR #20 (dev -> main) merged with all 12 checks green (merge commit on main). Full API suite 803 pass; web e2e 428 pass; screenshots in docs/screenshots/phase-12.
- T12.2 — org chart canvas, list view, Unassigned section, GET /organogram.pdf (7cb5219).
- T12.1 — org chart tree API and hierarchy levels CRUD (eb26aef).
- C1.3.1 — interview invites carry ORGANIZER (fix 25c7f7d). AUDIT-1 PASS on round 3.

## Current task
- T13.1 — Course model, minimal editor, course player (micro_plan.md, tier S)
  - [ ] 1. global courses (sections, quiz, sources, reviewed date, OGL attribution) + tenant learning_assignments; migration
  - [ ] 2. minimal super-admin course editor under web/app/(admin)/platform/courses/ (copy platform/dossier-links)
  - [ ] 3. course player: section by section, progress saved, keyboard friendly, quiz with pass mark
  - [ ] tests: progress survives reload; quiz below pass mark does not complete
- Resume note: nothing written yet for T13.1 at this point. `git status`; if partial files exist, finish the unchecked steps.

## Next tasks
- T13.2 (if present), P13 gate, then Phase 14. AUDIT-2 stop is after P14 (big model).

## Health
- CI on dev: green (PR #20 all checks). CI on main: green (after the merge).
- Local checks: T12.x — API full suite 803 pass; web lint/typecheck/unit/e2e pass.

## Issues / suggestions
- No UI yet to create or edit hierarchy levels (plan 8.13 wants an editable list). Change role sheet has no level picker (employment-tab still says "available with the organogram"). Owner or a later task to decide where this goes.
- Org chart card text is small on wide charts until zoomed (the chart now opens at 100%, which helps on phones).
- ORGANIZER/ATTENDEE CN values use backslash escaping (as the attendee CN already did); RFC 5545 wants parameter values quoted. Not changed.
- Test-order issue: running tests/db/test_employee_employment.py + tests/test_openapi.py + tests/db/test_auth_endpoints.py together gives 18 auth errors. The full suite in default order passes. Not investigated.
- Turnstile: production must set the site key (web) and secret (API) together.
- PR #16 (dependabot, python deps) is still open; not ours, left alone.

## Strategy / decisions taken
- Org chart permission: GET /organogram and /organogram/levels need organogram.level.read; writes need organogram.level.write.
- Tree: current assignment = effective today; people in active or on_leave only. No manager in the chart, or a loop of managers, puts a person under `unassigned`.
- Assignments validate organogram_level_id against the company (FK RESTRICT, migration 0034).
- Org chart UI: SVG canvas (CSP forbids inline styles, so cards are foreignObject with transform). Opens at 100%; "Fit the whole chart" button for overview. Search centres via an imperative handle, not an effect.
- The chart's top-level people (no manager) are shown under "Unassigned", per the plan's wording.

## Owner actions needed
- Phase 23: add a Cloudflare rate-limit rule for /careers/* (the API cannot tell visitors apart on server-rendered pages).
