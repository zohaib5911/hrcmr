# STATUS
Updated: 2026-11-08 02:59 (Europe/London)    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: see git log

State: IN PROGRESS — P16 gate (S)

## Last completed
- T16.5 — Delete account (API, migration 0047, purge executor, web /company/delete-account).
- T16.4 — Data export.
- T16.3 — Billing page and cancel with refund.
- T16.2 — Entitlements and payment-failed grace.
- T16.1 — Stripe integration and webhooks.

## Current task
- P16 — Phase 16 gate (S)
  - [ ] 1. Stripe test-mode keys present in `.env` (checked: no `.env` file, STRIPE_* not set) — BLOCKED, owner action
  - [ ] 2. Recipe R7 step 1: full API suite, web lint/typecheck/unit/e2e
  - [ ] 3. e2e: delete-account (start → code from Mailpit → scheduled → withdraw)
  - [ ] 4. e2e: billing page (plan card, cancel dialog; no Stripe call)
  - [ ] 5. Recipe R7 step 2: screenshots 390 + 1280, light + dark, docs/screenshots/phase-16/
  - [ ] 6. Recipe R7 step 3: 5-line phase summary in PROGRESS.md
  - [ ] 7. Stripe test-mode E2E (both plans, refund, cancel, failed payment, webhook replay) — BLOCKED until keys exist
- Resume note: start with step 2 (full API suite: `cd api && uv run pytest -q`; run in background, record counts). Steps 3–6 follow. Do not run DB pytest and Playwright at the same time.

## Next tasks
- P16 step 7 (Stripe E2E) once owner adds test keys; then tick P16, open PR dev → main, watch checks.

## Health
- CI on dev: not watched yet    CI on main: green (PR #23)
- Local checks run: none yet this session.

## Issues / suggestions
- (P16) Owner action: no `.env` in the repo. Put STRIPE_SECRET_KEY (rk_test_…), STRIPE_WEBHOOK_SECRET (from `stripe listen`), STRIPE_PRICE_ANNUAL and STRIPE_PRICE_TEN_YEAR in `.env` (see deployment-requirements.txt §5.4). Do not paste the values in chat.
- (T16.5) Test isolation: tests/db/test_billing.py counts payment_failed mail across the whole outbox (fails if test_email.py runs before it).
- (T16.3) Stripe's API version is not pinned; verify the invoice payment-intent field in test mode at step 7.
- (T16.2) A lapsed annual plan still says "annual" in /auth/me.
- (pre-existing) tests/test_openapi.py + tests/db/test_reports.py in one pytest call gives "fixture 'database' not found". Run them in separate calls if it appears.

## Strategy / decisions taken
- (P16) Stripe E2E is not faked: it stays BLOCKED until the owner's test keys exist. Everything else in R7 runs now.
- (P16) The PR dev → main is not merged while step 7 is open, because the gate's definition includes the Stripe E2E.

## Owner actions needed
- Add Stripe **test-mode** keys to `.env`: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ANNUAL, STRIPE_PRICE_TEN_YEAR (names in deployment-requirements.txt). Tell me when they are in place; the values stay out of chat.
- Confirm (from T16.3/T16.4): 10-year plans cannot be cancelled in-app after 14 days; bank numbers and sort codes are left out of the export; the export e-mail link needs a signed-in session.
