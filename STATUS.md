# STATUS
Updated: 2026-11-02 20:00 (Europe/London)    Agent: Codex    Branch: dev    Commit: 7f14225
State: IN PROGRESS

## Last completed
- T6.4 — Personal tab: details, address with postcode lookup, emergency contacts, NI/passport/bank masked with password-check reveal

## Current task
- T6.5 — Employment tab (hire date change with reason, effective-dated assignments + history, responsibilities, previous employment, education, training, memberships)
  - [x] Read requirements; API lint/types and web lint/types pass; DB baseline running with local service access
  - [ ] Employment API and tests
  - [ ] Employment tab UI
  - [ ] Employment e2e and final checks
- Resume note: add tab in web/components/employees/profile-page.tsx (follow personal-tab.tsx: Section, useSubmit, FormSheet); API goes in a new api/app/modules/employees/employment_router.py registered in app/main.py like personal_router. Tables already exist (migration 0013). Salary is T6.6, not here.

## Next tasks
- T6.6, T6.7, T6.8, then Phase 6 gate

## Health
- CI on dev: latest run green; T6.4 commit not yet run    CI on main: RED (flaky audit-export test, fixed on dev in the T6.1 branch; goes green when dev merges)
- Local checks run: API 380 pass, web unit 755 pass, ruff/mypy/eslint/tsc clean (before the last edits)

## Issues / suggestions
- Remove the certifi exception after 2026-11-06
- Dependabot #5 open: merge when CI is green

## Strategy / decisions taken
- T6.4: employees edit own details (profile.write_own) but not identity/bank; reveal and identity edit need a password check (step-up); NI example in forms is AB 12 34 56 C because QQ is not an issued prefix
- Relay mode; AI features hidden unless ANTHROPIC_API_KEY is set; Ask Mady deferred
- style-src-attr 'unsafe-inline' accepted (animation library)
- e2e: API server never reused locally; sign-ups send X-Real-IP (test API trusts 127.0.0.0/8) so the 5/hour sign-up limit stays on

## Owner actions needed
- None blocking. Protect `main` (require PR + CI passed); enable private vulnerability reporting.
