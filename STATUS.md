# STATUS
Updated: 2026-11-02 15:30 (Europe/London)    Agent: Claude Code    Branch: dev    Commit: see git log
State: IN PROGRESS

## Last completed
- T5.3 — two-step policy and role viewer (T5.1, T5.2 done before it)

## Current task
- Phase 5 gate
  - [ ] Full suites once (API, web unit, Playwright incl. design, guard scripts)   <- start here
  - [ ] Screenshots of /company/users at 390 and 1280, light and dark, into docs/screenshots/phase-5/ (extend web/tests/e2e/phase4-screenshots.spec.ts style)
  - [ ] Phase 5 summary in PROGRESS.md, tick the gate, PR dev -> main, merge when CI is green
- Resume note: the gate summary format is the Phase 4 one in PROGRESS.md. After the gate: T6.1 (employees); remember the link/unlink-employee picker for User Access.

## Next tasks
- T6.1, T6.2, T6.3

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
