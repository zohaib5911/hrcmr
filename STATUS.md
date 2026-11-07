# STATUS
Updated: 2026-11-07 04:23, Europe/London    Agent: Claude Code (Opus 5.5, BIG)    Branch: dev    Commit: see git log
State: HANDED OVER — audit passed (AUDIT-1 round 3: 0 P0 / 0 P1 / 1 P2); small model next

## Last completed
- AUDIT-1: round 1 (1/5/1), round 2 (0/3/1) and round 3 (0/0/1, PASS). All P0/P1 fixed on dev; tag audit-pass-1.
- PR #18 (Phase 11) merged to main. PR #19 (audit fixes) merges once its CI is green.

## Current task
- none.

## Next tasks
- C1.3.1 (P2, small model): ORGANIZER line in interview invites (changesneeded.md).
- Then Phase 12: T12.1, T12.2, P12.

## Health
- CI on dev: PR #19 re-run after the company.spec toast locator fix. CI on main: green (PR #18).
- Local checks: API 796 pass, ruff/mypy clean; web unit 777, lint, typecheck, build, gen:api clean; company, recruitment and careers browser specs pass.

## Issues / suggestions
- Turnstile: production must set the site key (web) and secret (API) together; with no secret the verifier accepts any token.
- Accepting an offer does not move the application to Offer Accepted on its own (plan silent).
- rota.published is missing from notifications/router.py _kinds (pre-existing).
- Pushing to dev while a gate PR runs restarts its CI; batch pushes during gates.
- Toast text appears twice (visible + screen-reader announcer): match toasts with exact: true in browser tests.
- AUDIT-2 should be run by a fresh session; AUDIT-1 rounds 2–3 were checked by the model that wrote the fixes.

## Strategy / decisions taken
- Hired is set only by Convert; no stage moves into or out of Hired.
- Interview invites: the .ics travels in the encrypted outbox payload and is attached as invite.ics; staff get the whole panel, the candidate's copy names only them (same UID).
- Careers apply is multipart; CV (PDF/DOC/DOCX, 10 MB) via FileService.store_public (shared checks with staff uploads). Refused public CVs are not audit-logged.
- Careers logo: has_logo + public GET /public/careers/{slug}/logo. Only the logo is rate-limited in the API; server-rendered careers pages are limited at the edge.
- Body limits: BodyLimitMiddleware accepts whole-path regex keys; tests/test_body_limits.py guards every multipart route.

## Owner actions needed
- Phase 23: add a Cloudflare rate-limit rule for /careers/* (the API cannot tell visitors apart on server-rendered pages).
