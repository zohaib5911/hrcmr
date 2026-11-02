# STATUS
Updated: 2026-11-02 15:30 (Europe/London)    Agent: Claude Code    Branch: dev    Commit: see git log
State: IN PROGRESS

## Last completed
- T5.2 — invitations, role change, suspend/reactivate, two-step reset (link/unlink employee deferred to T6.1: no employees table yet)

## Current task
- T5.3 — MFA policy setting and "What can each role do?" viewer
  - [ ] API: GET/PUT two-step policy on /company (companies.mfa_policy exists); audit; Company Admin only
  - [ ] API: GET /roles/matrix generated from rbac_matrix.py
  - [ ] Web: policy radio cards + role viewer on /company/users (or sub-page)   <- start with the API
- Resume note: policy values optional/admins/all are in app/modules/auth/policy.py; the matrix is app/core/rbac_matrix.py. T6.1 must add the link/unlink employee picker to User Access (api/app/modules/access, web/components/company/user-access-page.tsx).

## Next tasks
- T5.3, T6.1, T6.2

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
