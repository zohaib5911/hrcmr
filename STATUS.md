# STATUS
Updated: 2026-11-07 10:20, Europe/London    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: afa2d28

State: IN PROGRESS

## Last completed
- C1.3.1 — interview invites carry ORGANIZER (fix 25c7f7d, ticked afa2d28). AUDIT-1 PASS on round 3 (0 P0 / 0 P1).
- AUDIT-1: round 1 (1/5/1), round 2 (0/3/1) and round 3 (0/0/1, PASS). tag audit-pass-1.

## Current task
- T12.1 — Tree API and hierarchy levels (micro_plan.md, tier S)
  - [ ] 1. GET /organogram: tree on current assignments, unassigned list, cycle-safe; RTW chips only with employee.rtw.read
  - [ ] 2. organogram_levels table + CRUD /organogram/levels (ordered, default "Director" seeded at signup and in the migration)
  - [ ] tests: 3-level fixture tree, cycle test, cross-tenant isolation; then ruff/mypy and related tests
- Resume note: nothing written yet for T12.1 at this point. Look at `git status`; if files exist under api/app/modules/organogram/, finish the unchecked items.

## Next tasks
- T12.2, P12 (phase gate).

## Health
- CI on dev: PR #19 re-run after the company.spec toast locator fix. CI on main: green (PR #18).
- Local checks: C1.3.1 — ics 3, interviews DB 2, recruitment+interview set 149 pass; ruff/mypy clean.

## Issues / suggestions
- Turnstile: production must set the site key (web) and secret (API) together; with no secret the verifier accepts any token.
- Accepting an offer does not move the application to Offer Accepted on its own (plan silent).
- rota.published is missing from notifications/router.py _kinds (pre-existing).
- Pushing to dev while a gate PR runs restarts its CI; batch pushes during gates.
- Toast text appears twice (visible + screen-reader announcer): match toasts with exact: true in browser tests.
- ORGANIZER/ATTENDEE CN values use backslash escaping (as the attendee CN already did); RFC 5545 wants parameter values quoted. Not changed; consider later.
- employment_router.py still refuses organogram_level_id ("Hierarchy levels are not available yet."). Left as is in T12.1 (plan has no task that wires levels to assignments yet).

## Strategy / decisions taken
- Hired is set only by Convert; no stage moves into or out of Hired.
- Interview invites: the .ics travels in the encrypted outbox payload and is attached as invite.ics; staff get the whole panel, the candidate's copy names only them (same UID).
- Organizer: company name plus the address part of sender_of(settings) (parseaddr).
- Org chart permission: GET /organogram and GET /organogram/levels need organogram.level.read (the only organogram read in the matrix); level writes need organogram.level.write.
- Org chart tree: current assignment = effective today (same rule as ReportsGraph); people in active or on_leave status only. A person with no manager, or whose manager is not in the tree, sits at the top under `unassigned`. Anyone left unreached by a cycle is put under `unassigned` too, so nobody disappears.

## Owner actions needed
- Phase 23: add a Cloudflare rate-limit rule for /careers/* (the API cannot tell visitors apart on server-rendered pages).
