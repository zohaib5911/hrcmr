# STATUS
Updated: 2026-11-07 09:54, Europe/London    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: 4a65785

State: IN PROGRESS

## Last completed
- AUDIT-1: round 1 (1/5/1), round 2 (0/3/1) and round 3 (0/0/1, PASS). All P0/P1 fixed on dev; tag audit-pass-1.
- PR #18 (Phase 11) merged to main. PR #19 (audit fixes) merges once its CI is green.

## Current task
- C1.3.1 — ORGANIZER line in interview invites (changesneeded.md, P2, tier S)
  - [x] read ics.py, router.py invite path, outbox.sender_of, tests
  - [ ] add organizer arg to interview_ics; write ORGANIZER after DTSTAMP
  - [ ] pass company name + sender address from _invite_text (3 call sites)
  - [ ] tests/test_interview_ics.py asserts ORGANIZER; run tests/db/test_interviews.py
  - [ ] tick C1.3.1 in changesneeded.md with fix commit
- Resume note: if cut off, `git status` shows the partial edit; finish the four unchecked steps above, then run `bash .agent/next.sh`.

## Next tasks
- Then Phase 12: T12.1, T12.2, P12.

## Health
- CI on dev: PR #19 re-run after the company.spec toast locator fix. CI on main: green (PR #18).
- Local checks: not run yet for C1.3.1.

## Issues / suggestions
- Turnstile: production must set the site key (web) and secret (API) together; with no secret the verifier accepts any token.
- Accepting an offer does not move the application to Offer Accepted on its own (plan silent).
- rota.published is missing from notifications/router.py _kinds (pre-existing).
- Pushing to dev while a gate PR runs restarts its CI; batch pushes during gates.
- Toast text appears twice (visible + screen-reader announcer): match toasts with exact: true in browser tests.
- ORGANIZER/ATTENDEE CN values use backslash escaping (as the attendee CN already did); RFC 5545 wants parameter values quoted. Not changed here; consider for a later fix.

## Strategy / decisions taken
- Hired is set only by Convert; no stage moves into or out of Hired.
- Interview invites: the .ics travels in the encrypted outbox payload and is attached as invite.ics; staff get the whole panel, the candidate's copy names only them (same UID).
- Organizer: company name plus the address part of sender_of(settings) (parseaddr), so the invite shows the company as organizer.

## Owner actions needed
- Phase 23: add a Cloudflare rate-limit rule for /careers/* (the API cannot tell visitors apart on server-rendered pages).
