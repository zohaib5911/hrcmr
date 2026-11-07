# STATUS
Updated: 2026-11-07 03:54, Europe/London    Agent: Claude Code (Opus 5.5, BIG)    Branch: dev    Commit: 0044639+
State: HANDED OVER — audit fixes ready (AUDIT-1 round 2: 0 P0 / 3 P1 / 1 P2 in changesneeded.md)

## Last completed
- AUDIT-1 round 1 (scope f37f781..a49307d): 1 P0, 5 P1, 1 P2 in changesneeded.md; all 7 fixed and ticked at the owner's request.
- PR #18 (Phase 11) merged to main as 1ea40b1 with all checks green.

## Current task
- none. next.sh shows C1.2.1 (FIX, S). PR #19 (round 1 fixes) is open; do not merge it until C1.2.1 and C1.2.2 are in.

## Next tasks
- C1.2.1–C1.2.4 (small model), then AUDIT-1 round 3 (big model, fresh session): scope audit-1-r2..HEAD.
- Then T12.1, T12.2, P12.

## Health
- CI on dev: fixes PR open (dev → main), waiting for checks. CI on main: green (PR #18).
- Local checks after fixes: API 792 pass, ruff/mypy clean; web unit 777, typecheck, lint, gen:api clean; recruitment + careers browser specs 5 pass.

## Issues / suggestions
- Public CV refusals are not audit-logged (no signed-in user, and the request writes nothing); staff upload refusals still are.
- Turnstile: production must set the site key (web) and secret (API) together; with no secret the verifier accepts any token.
- Accepting an offer does not move the application to Offer Accepted on its own (plan silent).
- rota.published is missing from notifications/router.py _kinds (pre-existing).
- Pushing to dev while a gate PR runs restarts its CI; batch pushes during gates.

## Strategy / decisions taken
- Hired is set only by Convert; no stage moves into or out of Hired.
- Interview invites: the .ics text travels in the encrypted outbox payload under "ics" and is attached as invite.ics (text/calendar; method=REQUEST) at delivery; Message gained attachments (Resend + SMTP).
- Careers apply is multipart form data; the CV (PDF/DOC/DOCX, 10 MB) uses FileService.store_public, which shares FileService._vet with staff uploads.
- Careers logo: has_logo + public GET /public/careers/{slug}/logo (copies GET /company/logo), not a signed storage URL, so the CSP is unchanged.
- Public careers reads: 120 per minute per connection.

## Owner actions needed
- None.
