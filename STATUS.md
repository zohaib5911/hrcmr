# STATUS
Updated: 2026-11-08 09:46 (Europe/London)    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: see git log

State: IN PROGRESS

## Last completed
- P16 gate R7 steps 1–3 — API 1254, web lint/typecheck/unit 786, web e2e 436 passed, 16/16 screenshots, PROGRESS summary (Opus parked Stripe E2E in leftover.md L1).
- T16.6 — Deletion code e-mail sent after commit through the app mailer (Opus).
- T16.5 — Delete account (Opus).
- T16.4 — Data export.
- T16.3 — Billing page and cancel with refund.
- T16.2 — Entitlements and payment-failed grace.
- T16.1 — Stripe integration and webhooks.

## Current task
- P16 — Phase 16 gate (S), not ticked
  - [x] R7 steps 1–3 (see Last completed)
  - [ ] R7 step 4: PR dev → main, watch checks, merge only when all green, tick P16   <- here
  - [~] Stripe test-mode E2E — PARKED in `leftover.md` L1 (owner has no test keys)
- Resume note: `gh pr create --base main --head dev` (body from the P16 summary in PROGRESS.md); `gh pr checks <n> --watch`; merge with `gh pr merge <n> --merge` only when every check is green; then tick P16 in micro_plan.md and PROGRESS.md; then T17.1 (S!).
- Check before opening: main has 11 merge commits and no non-merge commits that dev lacks; the main-only lines are stale copies of files dev has since changed, so the PR carries dev's content.

## Next tasks
- P16: PR dev → main and tick.
- T17.1 (S!) platform admin auth and admin host routing (micro_plan L387).
- leftover.md L1 (Stripe E2E) when the owner has test keys; before Phase 23.

## Health
- CI on dev: not run yet for P16 (PR about to open). Workflows: ci.yml, security.yml.
- CI on main: green at PR #23 (P15). Open Dependabot PRs #24 (uv) and #5 (npm) — not part of this gate.
- Local checks run this session: API full 1254 pass; web lint 0 warnings; typecheck clean; unit 786 pass; full web e2e 436 pass, 200 skipped, 0 fail.

## Issues / suggestions
- (T16.6) The delete-account page header breadcrumb reads "Company / Company" with title "Company"; the page h1 is right. Cosmetic, for the auditor.
- (T16.6) `deletion_scheduled`(+support), `deletion_withdrawn` and `account_deleted` still use the outbox-in-transaction helper; e2e cannot see them until the minute sweep runs.
- (T16.5) Test isolation: tests/db/test_billing.py counts payment_failed mail across the whole outbox.
- (T16.3) Stripe's API version is not pinned; verify the invoice payment-intent field in test mode (leftover.md L1).
- (T16.2) A lapsed annual plan still says "annual" in /auth/me.
- (pre-existing) tests/test_openapi.py + tests/db/test_reports.py in one pytest call gives "fixture 'database' not found".

## Strategy / decisions taken
- (T16.6) Only `deletion_code` moved to the app mailer (sent after commit); the other three deletion notices stay as outbox rows in the same transaction.
- (P16, owner) No Stripe test keys yet: Stripe E2E parked in leftover.md L1; the P16 gate continues without it. No mocked run is counted as the test-mode E2E.
- (P16) Heading fix: page-level cards use `headingLevel={2}`; cards inside the "Choose a plan" h2 section keep h3.

## Owner actions needed
- When you have Stripe test keys: put them in `.env` (names in leftover.md L1) and tell an agent to do leftover.md L1. Not blocking.
- Confirm (from T16.3/T16.4): 10-year plans cannot be cancelled in-app after 14 days; bank numbers and sort codes are left out of the export; the export e-mail link needs a signed-in session.
