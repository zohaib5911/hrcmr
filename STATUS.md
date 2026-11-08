# STATUS
Updated: 2026-11-08 09:30 (Europe/London)    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: see git log

State: BLOCKED — owner action (Stripe test keys in `.env` for the P16 Stripe test-mode E2E)

## Last completed
- P16 gate, partly — R7 steps 1–3 done (API 1254, web lint/typecheck/unit 786, full web e2e 436 passed; 16/16 screenshots; PROGRESS summary written). Gate tick and PR held.
- T16.6 — Deletion code e-mail sent after commit through the app mailer (Opus).
- T16.5 — Delete account (Opus, earlier session).
- T16.4 — Data export.
- T16.3 — Billing page and cancel with refund.
- T16.2 — Entitlements and payment-failed grace.
- T16.1 — Stripe integration and webhooks.

## Current task
- P16 — Phase 16 gate (S), not ticked
  - [x] R7 step 1a: full API suite 1254 passed, 0 failed (exit 0, 412 s)
  - [x] R7 step 1b: web lint (0 warnings), typecheck clean, unit 786 passed; full web e2e 436 passed, 200 skipped, exit 0
  - [x] R7 step 2: screenshots docs/screenshots/phase-16/ — 16 of 16
  - [x] R7 step 3: phase summary in PROGRESS.md (heading + 4 bullets, with the open item)
  - [ ] R7 step 4: PR dev → main — held until the Stripe E2E passes (gate incomplete)
  - [ ] Stripe test-mode E2E (both plans, refund, cancel, failed payment, webhook replay) — BLOCKED: no Stripe test keys (no `.env`; STRIPE_* not set in the environment)
- Resume note: all local P16 checks are green. Only the Stripe test-mode E2E remains. When the owner adds the keys to `.env`, run the Stripe E2E (both plans, refund, cancel, failed payment, webhook replay, using `stripe listen` for the webhook secret). Then tick P16 in micro_plan.md and PROGRESS.md, rewrite STATUS, and open the PR dev → main (`gh pr create --base main --head dev`), wait for checks, and merge only when green.

## Next tasks
- P16: Stripe E2E (owner keys), then gate tick and PR.
- P17 (after P16 gate): T17.1 (S!) platform admin auth and admin host routing.

## Health
- CI on dev: not run for P16 (no PR open). Last PR was #23 (P15, green on main).
- CI on main: green (PR #23)
- Local checks run this session: API full 1254 pass; web lint 0 warnings; typecheck clean; unit 786 pass; full web e2e 436 pass, 200 skipped, 0 fail.

## Issues / suggestions
- (T16.6) The delete-account page header breadcrumb reads "Company / Company" with title "Company" (seen in the screenshot); the page h1 is right. Cosmetic, for the auditor.
- (T16.6) At 1280 px the scheduled-deletion line is in the DOM twice (one hidden); the screenshot spec now scopes to #main.
- (T16.6) `deletion_scheduled`(+support), `deletion_withdrawn` and `account_deleted` still use the outbox-in-transaction helper. Works in production (sweep every minute); e2e cannot see them until the sweep runs. Only the code e-mail was moved.
- (T16.5) Test isolation: tests/db/test_billing.py counts payment_failed mail across the whole outbox.
- (T16.3) Stripe's API version is not pinned; verify the invoice payment-intent field in test mode at the Stripe step.
- (T16.2) A lapsed annual plan still says "annual" in /auth/me.
- (pre-existing) tests/test_openapi.py + tests/db/test_reports.py in one pytest call gives "fixture 'database' not found".
- (P16, fixed) billing page h3 cards directly under h1 failed axe heading-order: now h2 on the page-level cards (billing + delete-account).

## Strategy / decisions taken
- (T16.6) Only `deletion_code` moved to the app mailer (sent after commit). The other three deletion notices stay as outbox rows in the same transaction: they are notices, not a way in, so a minute's delay is fine and they commit atomically with the state change.
- (P16) Stripe E2E is not faked: stays BLOCKED until the owner's test keys exist. No mocked run is counted as the test-mode E2E.
- (P16) The PR dev → main is not opened until the gate is complete (Stripe E2E), so the gate is not merged half-done.
- (P16) Heading fix: page-level cards use `headingLevel={2}` (existing convention); cards inside the "Choose a plan" h2 section keep h3.

## Owner actions needed
- Add Stripe **test-mode** keys to `.env` (there is no `.env` in the repo yet; copy `.env.example`): STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ANNUAL, STRIPE_PRICE_TEN_YEAR (names in deployment-requirements.txt). Paste the values into the file yourself, not into chat. Then type "Read AGENTS.md and continue" in a small model.
- Confirm (from T16.3/T16.4): 10-year plans cannot be cancelled in-app after 14 days; bank numbers and sort codes are left out of the export; the export e-mail link needs a signed-in session.
