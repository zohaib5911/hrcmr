# STATUS
Updated: 2026-11-07 17:30, Europe/London    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: 9ab9a8c
State: IN PROGRESS

## Last completed
- T10.2 — Seven fresh private worker XLSX reports complete (Codex, 2026-11-04).

## Current task
- T10.3 — Policies and sign-offs (finish; steps 1–4 done by Codex)
  - [ ] step 5: POST /policies/{id}/remind (pending only) + overdue job + new-starter assignment; tests in api/tests/db/test_policies.py
  - [ ] step 6: UI — /policies list, 3-step New document sheet, /policies/[id] detail, My Documents policy section
  - [ ] step 7: R6 spec web/tests/e2e/policies.spec.ts (send → sign → admin sees Signed; employee blocked from /policies)
  - [ ] Done when: steps pass; pnpm gen:api:check clean; affected API tests green
- Resume note: docker compose up (stack healthy). Step 5 in progress: service.py gets remind/overdue/new-starter functions, router gets /remind, jobs/compliance-style job registered in jobs/scheduled.py, hook in employees/router.py create_employee.

## Next tasks
- T10.4 — Draft with AI feature-flagged UI/API contract
- Phase 10 gate — full validation/screenshots/green PR

## Health
- CI on dev: green (all12;41737189830)    CI on main: green
- Local checks run: none yet this session

## Issues / suggestions
- Rota publish inserts rota.published notifications but notifications/router.py _kinds omits that kind (not part of T10.3; left alone).
- Never overlap DB pytest and Playwright (shared PostgreSQL role passwords).

## Strategy / decisions taken
- Overdue is a stored status flip (pending→overdue) by the daily job; accept still works on overdue rows.
- New-starter assignment: one function used by the employee-create hook and the daily job; only policies with auto_send_new_starters on sent versions.

## Owner actions needed
- None.
