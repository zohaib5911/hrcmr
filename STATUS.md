# STATUS
Updated: 2026-11-07 06:30, Europe/London    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: pending (feat T10.3)
State: IN PROGRESS

## Last completed
- T10.3 — Policies and sign-offs: remind, overdue job, new-starter assignment, /policies wizard/list/detail, My Documents policy viewer/sign/receipt, Playwright spec green.

## Current task
- none (T10.3 closed; next block is T10.4 per next.sh)

## Next tasks
- T10.4 — "Draft with AI" UI and API contract (feature-flagged)
- Phase 10 gate — full validation/screenshots/green PR
- AUDIT-1 after P11

## Health
- CI on dev: fixed mypy --strict error from T10.2 test (6e8b92f); last green run was before T10.2 — re-check on push
- CI on main: green (PR15)
- Local checks run: API policies 15 pass; related worker/notifications/employees/profile/rbac 34 pass; reports 6 pass; mypy clean; ruff clean. Web typecheck/lint clean; web unit 777 pass; gen:api:check clean; Playwright policies.spec 1 pass.

## Issues / suggestions
- Rota publish inserts rota.published notifications but notifications/router.py _kinds omits that kind (not in T10.3; left alone).
- Policy notify() uses scope_for(role,"policy.acceptance.read") which resolves to _own for employees (works), but the check reads oddly; consider a clearer read_own check.
- Overdue notices go to the employee only; admins see overdue via the detail page counts, not a notification.
- Audience pickers load full department/location lists and up to the first page of employees for named people; large companies may want server search for named people.
- Never overlap DB pytest and Playwright (shared PostgreSQL role passwords).

## Strategy / decisions taken
- Overdue is a stored status flip (pending→overdue) by policies_overdue_daily at 06:15 (same slot as leave/learning overdue jobs in plan); the API status and count honour the stored overdue as well as the due date.
- Remind targets people who have not accepted or signed a sent version, including overdue ones; it is rejected for drafts and archived versions (409).
- New-starter assignment: one function used by the employee-create hook (same transaction) and the daily job (catch-up for anyone who joined an audience later); existing acceptances are never duplicated.
- Policy viewer iframe loads the API's own /policies/own/{id}/view proxy (cookie auth); web CSP frame-src adds only the configured API origin.
- The /policies page is gated to policy.document.read (HR), so employees see an explanation instead of the list.

## Owner actions needed
- None.
