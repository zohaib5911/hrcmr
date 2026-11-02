# STATUS
Updated: 2026-11-02 15:30 (Europe/London)    Agent: Claude Code    Branch: dev    Commit: see git log
State: IN PROGRESS

## Last completed
- T6.3 — employee profile header and Overview tab, lifecycle, 48 h opt-out, guarded delete

## Current task
- T6.4 — Personal tab (details, address with postcode lookup, emergency contacts, NI/passport and bank masked with step-up reveal)
  - [x] API: migration 0014 (relationship list), api/app/modules/employees/personal_router.py + personal_schemas.py, 3 tests pass, web schema regenerated
  - [ ] web: Personal tab in web/components/employees/profile-page.tsx (new file personal-tab.tsx), step-up dialog for reveal   <- here
  - [ ] e2e: extend web/tests/e2e/employees.spec.ts
- Resume note: endpoints GET/PUT /employees/{id}/personal, PUT address, POST/PUT/DELETE contacts, PUT identity, PUT bank, POST reveal {field: identity|bank} (needs POST /auth/step-up {password} first), GET /employee-lookups/postcode/{pc}. Use useCan() for profile.write / sensitive_data.write; response `sensitive_visible` says whether to show identity/bank.

## Next tasks
- T6.5

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
