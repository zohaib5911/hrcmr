# STATUS
Updated: 2026-11-08 (Europe/London)    Agent: Claude Code (Opus 5.5, BIG)    Branch: dev    Commit: see git log

State: HANDED OVER — small model next

## Last completed
- T16.6 — Deletion code e-mail sent after commit through the app mailer (Opus).
- T16.5 — Delete account (Opus, earlier session).
- T16.4 — Data export.
- T16.3 — Billing page and cancel with refund.
- T16.2 — Entitlements and payment-failed grace.
- T16.1 — Stripe integration and webhooks.

## Current task
- P16 — Phase 16 gate (S), not ticked
  - [x] R7 step 1a: full API suite 1254 passed, 0 failed (exit 0)
  - [x] billing e2e (2 tests) passes; billing added to the shell spec BUILT set
  - [x] web lint (0 warnings), typecheck, unit 786 pass
  - [x] delete-account e2e: passes after T16.6
  - [ ] R7 step 1b: full web e2e: 433 passed, 200 skipped, 3 failed before the billing fixes; 2 of the 3 now fixed (billing strict-mode, shell BUILT). account-deletion.spec.ts now passes too; rerun the full web e2e once to confirm
  - [x] R7 step 2: screenshots docs/screenshots/phase-16/ — 16 of 16 (scheduled shots taken after T16.6; spec scoped to #main at 1280)
  - [ ] R7 step 3: 5-line phase summary in PROGRESS.md — not written; gate not complete
  - [ ] R7 step 4: PR dev → main — not opened; gate not complete
  - [ ] Stripe test-mode E2E (both plans, refund, cancel, failed payment, webhook replay) — BLOCKED: no Stripe test keys (no .env; STRIPE_* not set)
- Resume note: T16.6 done. Rerun the full web e2e once (R7 1b), then the Stripe test-mode E2E needs the owner's keys (BLOCKED if missing); then summary + PR.

## Next tasks
- P16 (S) steps above.

## Health
- CI on dev: RED locally — account-deletion.spec.ts fails (T16.6). Not pushed to CI yet (no PR open).
- CI on main: green (PR #23)
- Local checks run this session: API full 1254 pass; web lint 0 warnings; typecheck clean; unit 786 pass; full web e2e 433 pass / 3 fail (2 fixed since, see above); billing e2e 2 pass; shell billing 1 pass.

## Issues / suggestions
- (T16.6) The delete-account page header breadcrumb reads "Company / Company" with title "Company" (seen in the screenshot); the page h1 is right. Cosmetic, for the auditor.
- (T16.6) At 1280 px the scheduled-deletion line is in the DOM twice (one hidden); the screenshot spec now scopes to #main.
- (T16.6) The deletion code e-mail is written as an outbox row, not sent by the app mailer. Production works (sweep every minute) but it is slow, and e2e cannot see it. Details in micro_plan T16.6.
- (T16.6) `deletion_scheduled`, `deletion_withdrawn`, `account_deleted` use the same outbox-in-transaction helper (`_email`). Same fix class; decide in T16.6.
- (P16 e2e) `web/tests/e2e/account-deletion.spec.ts` is the only failing test on dev. Not skipped on purpose: it is the right expectation, and it should pass after T16.6.
- (P16) The delete-scheduled screenshots and the confirm/withdraw part of the e2e cannot run until the code e-mail is delivered in e2e.
- (T16.5) Test isolation: tests/db/test_billing.py counts payment_failed mail across the whole outbox.
- (T16.3) Stripe's API version is not pinned; verify the invoice payment-intent field in test mode at the Stripe step.
- (T16.2) A lapsed annual plan still says "annual" in /auth/me.
- (pre-existing) tests/test_openapi.py + tests/db/test_reports.py in one pytest call gives "fixture 'database' not found".
- (P16, fixed) billing page h3 cards directly under h1 failed axe heading-order: now h2 on the page-level cards (billing + delete-account). Same convention as 10 other places.

## Strategy / decisions taken
- (T16.6) Only `deletion_code` moved to the app mailer (sent after commit). `deletion_scheduled`(+support), `deletion_withdrawn` and `account_deleted` stay as outbox rows in the same transaction: they are notices, not a way in, so a minute's delay is fine and they commit atomically with the state change.
- (P16) Stripe E2E is not faked: stays BLOCKED until the owner's test keys exist.
- (P16) The PR dev → main is not opened until the gate is complete (delete e2e and Stripe E2E), so CI on the PR is not red.
- (P16) Heading fix: page-level cards use `headingLevel={2}` (existing convention); cards inside the "Choose a plan" h2 section keep h3.
- (P16) Billing e2e does not confirm the cancel dialog (no Stripe call). The "1 year plan" assertion takes the first match because the name appears twice on the page.
- (P16) Screenshot spec for billing/delete uses the API for the scheduled state only if T16.6 is done; the scheduled shots are not faked.

## Owner actions needed
- Add Stripe **test-mode** keys to `.env`: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ANNUAL, STRIPE_PRICE_TEN_YEAR (names in deployment-requirements.txt). The values stay out of chat. There is no `.env` in the repo yet.
- Confirm (from T16.3/T16.4): 10-year plans cannot be cancelled in-app after 14 days; bank numbers and sort codes are left out of the export; the export e-mail link needs a signed-in session.
