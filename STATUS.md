# STATUS
Updated: 2026-11-02 15:30 (Europe/London)    Agent: Claude Code    Branch: dev    Commit: see git log
State: IN PROGRESS

## Last completed
- T6.2 — create page /employees/new, POST /employees, unique number rule

## Current task
- T6.3 — profile header, Overview tab, lifecycle status, 48 h opt-out, guarded permanent delete
  - [ ] read plan 8.3 profile section and 6.3   <- start here
- Resume note: employee code is api/app/modules/employees/ and web/components/employees/.

## Next tasks
- T6.4, T6.5

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
