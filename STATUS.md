# STATUS
Updated: 2026-11-07 11:30, Europe/London    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: eb26aef

State: IN PROGRESS

## Last completed
- T12.1 — org chart tree API and hierarchy levels CRUD (eb26aef). Full API suite 802 pass.
- C1.3.1 — interview invites carry ORGANIZER (fix 25c7f7d). AUDIT-1 PASS on round 3 (0 P0 / 0 P1).

## Current task
- T12.2 — Canvas, list view, unassigned section, PDF export (micro_plan.md, tier S)
  - [ ] 1. GET /organogram.pdf (R4, WeasyPrint, multi-page) with a 60-person API test
  - [ ] 2. web /organogram: canvas (pan drag, zoom buttons + pinch, search, inspector, visa toggle), plain SVG/CSS
  - [ ] 3. list view toggle, unassigned section, keyboard reachable; nav entry gated by permission
  - [ ] 4. R6 browser spec: search finds a person and opens inspector; typecheck/lint/unit checks
- Resume note: check `git status` and the last `wip(T12.2)` commit; finish the unchecked steps in order.

## Next tasks
- P12 (Phase 12 gate, S), then Phase 13.

## Health
- CI on dev: PR #19 re-run after the company.spec toast locator fix. CI on main: green (PR #18).
- Local checks: T12.1 — full API suite 802 pass; ruff/mypy clean; gen:api clean.

## Issues / suggestions
- Turnstile: production must set the site key (web) and secret (API) together; with no secret the verifier accepts any token.
- Accepting an offer does not move the application to Offer Accepted on its own (plan silent).
- rota.published is missing from notifications/router.py _kinds (pre-existing).
- Toast text appears twice (visible + screen-reader announcer): match toasts with exact: true in browser tests.
- ORGANIZER/ATTENDEE CN values use backslash escaping (as the attendee CN already did); RFC 5545 wants parameter values quoted. Not changed; consider later.
- Test-order issue: running tests/db/test_employee_employment.py + tests/test_openapi.py + tests/db/test_auth_endpoints.py together gives 18 auth errors (RATE_LIMITED/CSRF assertions). The full suite in default order passes (802). Likely global state from test_openapi; not investigated.

## Strategy / decisions taken
- Hired is set only by Convert; no stage moves into or out of Hired.
- Interview invites: the .ics travels in the encrypted outbox payload and is attached as invite.ics; staff get the whole panel, the candidate's copy names only them (same UID).
- Organizer: company name plus the address part of sender_of(settings) (parseaddr).
- Org chart permission: GET /organogram and GET /organogram/levels need organogram.level.read; level writes need organogram.level.write.
- Org chart tree: current assignment = effective today (same rule as ReportsGraph); people in active or on_leave status only. A person with no manager, or whose manager is not in the tree, sits at the top under `unassigned`. People in a loop of managers are also put at the top so nobody disappears.
- Assignments: organogram_level_id now validated against the company's levels (was refused as "not available yet"); FK added in migration 0034 with RESTRICT.

## Owner actions needed
- Phase 23: add a Cloudflare rate-limit rule for /careers/* (the API cannot tell visitors apart on server-rendered pages).
