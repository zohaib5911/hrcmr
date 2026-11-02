# STATUS
Updated: 2026-11-02 15:30 (Europe/London)    Agent: Claude Code    Branch: dev    Commit: see git log
State: IN PROGRESS

## Last completed
- T6.1 — employee tables, list, summary, archived list (RTW column/pill/filter deferred to T7.1)

## Current task
- T6.2 — create page `/employees/new` (essentials) and the unique-number rule
  - [ ] read plan 8.3 create section and 6.3   <- start here
  - [ ] API: POST /employees (audit, unique number ignoring case and spaces, hire date <= 12 months ahead)
  - [ ] Web: form, "New" button on the list + N shortcut, NSC side note; e2e can now create employees
- Resume note: list code is api/app/modules/employees/router.py and web/components/employees/employees-page.tsx. After T6.2 extend e2e employees.spec with a created employee.

## Next tasks
- T6.3, T6.4, T6.5

## Health
- CI on dev: not yet run for T6.1    CI on main: RED (flaky audit-export test, fixed on dev in the T6.1 branch; goes green when dev merges)
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
