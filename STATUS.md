# STATUS
Updated: 2026-11-02 15:30 (Europe/London)    Agent: Claude Code    Branch: dev    Commit: see git log
State: IN PROGRESS

## Last completed
- Phase 5 gate (T5.1 to T5.3): full suites green, summary written, PR dev -> main opened

## Current task
- T6.1 — Employee model + migrations (plan 6.3), list page with pills, filters, deep links, keyboard nav, summary line, archived list
  - [ ] read plan 6.3 and 8.x employees section   <- start here
- Resume note: add the link/unlink-employee picker to User Access (api/app/modules/access, web/components/company/user-access-page.tsx) once employees exist; Membership.employee_id has no foreign key yet (add it in the employees migration).

## Next tasks
- T6.2, T6.3, T6.4

## Health
- CI on dev: not yet run for T5.1    CI on main: green (PR #7 merged)
- Local checks run: API 380 pass, web unit 755 pass, ruff/mypy/eslint/tsc clean (before the last edits)

## Issues / suggestions
- Remove the certifi exception after 2026-11-06
- Dependabot #5 open: merge when CI is green

## Strategy / decisions taken
- Relay mode; AI features hidden unless ANTHROPIC_API_KEY is set; Ask Mady deferred
- style-src-attr 'unsafe-inline' accepted (animation library)
- e2e: API server never reused locally; sign-ups send X-Real-IP (test API trusts 127.0.0.0/8) so the 5/hour sign-up limit stays on

## Owner actions needed
- None blocking. Protect `main` (require PR + CI passed); enable private vulnerability reporting.
