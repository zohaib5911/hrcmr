# STATUS
Updated: 2026-11-02 15:30 (Europe/London)    Agent: Claude Code    Branch: dev    Commit: see git log
State: IN PROGRESS

## Last completed
- T5.1 — User Access list, filters and unlinked banner (GET /users, /company/users)

## Current task
- T5.2 — Invite flow, role change, suspend/reactivate, reset 2FA, link/unlink
  - [ ] API: invite (single-use link e-mail), pending invites in the list   <- start here
  - [ ] API: role change (last-admin protection), suspend/reactivate, reset two-step (step-up)
  - [ ] Web: Invite sheet, row actions menu
- Resume note: extend api/app/modules/access/router.py and web/components/company/user-access-page.tsx; invitations live in identity.Invitation (pre-tenant, via GlobalSession; see auth/invitations.py).

## Next tasks
- T5.2, T5.3, T6.1

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
