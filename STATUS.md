# STATUS
Updated: 2026-11-08 Europe/London    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: see git log

State: IN PROGRESS

## Last completed
- T16.3 — Billing page and cancel with refund. POST /billing/cancel: within 14 days a full refund of the first payment (Stripe Refunds, key refund-<payment intent>) then the subscription cancelled at once; after 14 days an annual plan cancels at period end (no refund); a 10-year plan after 14 days gets 409 NOTHING_TO_CANCEL. Web /company/billing built. Billing DB 13 pass; web lint, typecheck, unit 786 pass.
- T16.2 — Entitlements (402 PLAN_REQUIRED gate) and payment-failed grace.
- T16.1 — Stripe integration and webhooks.
- P15 — PR 23 merged to main (all checks green).

## Current task
- T16.4 — Data export (S!). Not started. Read micro_plan T16.4 block and plan.md L1091, L1460, API item 22.
  - [ ] 1. Read plan L1091 and API item 22; find existing worker/job pattern (e.g. rules_watch_daily job, email outbox) and private storage helper
  - [ ] 2. Step-up on the export request; worker builds zip (CSV per tenant table + documents) to private storage; 7-day e-mail link
  - [ ] 3. GET /companies/me/exports/{id}
  - [ ] 4. Tests: export holds only the requesting company's rows (two tenants); no step-up → refused
  - [ ] 5. Lint/typecheck/tests; tick micro_plan + PROGRESS; final commit
- Resume note: nothing written yet for T16.4. Start by reading the spec and the nearest existing worker (api/app/jobs or similar) before editing.

## Next tasks
- T16.4 (S!), T16.5 (B), P16 gate

## Health
- CI on dev: not watched (no PR open)    CI on main: green (PR #23)
- Local checks run for T16.3: billing DB 13 pass; guards (openapi, architecture, rbac, entitlements, body limits) 68 pass; web lint, typecheck, unit 786 pass.

## Issues / suggestions
- (T16.3) Stripe's API version is not pinned. The invoice's payment intent is read from `payment_intent` or from `payments` (2025 shape). Verify against Stripe test mode at the phase gate.
- (T16.3) Stripe only keys POST requests for idempotency; the immediate cancel (DELETE) has no key. A retry is safe because the endpoint reads the subscription first and skips the cancel once it has ended.
- (T16.3) The billing page is checked only by a temporary render test (deleted, not committed) plus lint and typecheck. No e2e spec renders it yet. Add one at the P16 gate.
- (T16.3) Prices in the page copy (£50 a year, £240 once) are text, not the Stripe price. Keep them in step with the price ids.
- (T16.2) A lapsed annual plan (past_due after grace) still says "annual" in /auth/me, so the free-plan banner does not show. The billing page shows the grace state.
- (T16.2) Test companies (raw inserts in tests/db) are on annual/active. A free-plan test must set plan = 'free' itself (see tests/db/test_billing.py fixture `free`).
- (T16.1) OpenAPI component names must be unique. After any new endpoint run `pnpm gen:api` in web and check that no names disappear.
- Body limits: every upload route must be in the limits table in api/app/main.py.
- Architecture rule: app code may not use any `.text` attribute (it is taken for raw SQL text()).
- Test harness: the rig's `two_companies` truncates users and companies cascade. Do not run DB suites in parallel.
- Pre-existing: OpenAPI already had five qualified AddressOut names. Not from SOC.

## Strategy / decisions taken
- (T16.3) Within 14 days: refund the first payment (annual: latest invoice's payment intent; 10-year: its payment intent), commit, then cancel the Stripe subscription at once. Refund key `refund-<payment_intent>`. Cancel-at-period-end key `cancel-period-<subscription>`.
- (T16.3) 10-year after 14 days: no renewal exists, so there is nothing to cancel. The endpoint answers 409 NOTHING_TO_CANCEL and the page says to contact support. Owner should confirm this reading.
- (T16.3) "Contact support" uses the same address as the e-mails (SUPPORT_EMAIL, else support@<domain>), returned in GET /billing/subscription as `support_email`.
- (T16.3) Choosing a plan is offered only on the free plan. A lapsed annual plan uses "Payment details and invoices" (the portal) to recover.
- (T16.3) Audit actions: billing.refunded (refund made) and billing.cancelled (cancel requested), both by the requesting user.
- (T16.2) "profile" in plan 8.16's exemption list is read as the company profile (company.profile.write), so a free company can complete its details before paying. /auth (own account) is never gated.
- (T16.2) Annual entitlement follows Stripe's status, not the stored period end.
- (T16.1) Stripe is called with httpx (no stripe SDK). Tests swap the transport.

## Owner actions needed
- Confirm: after 14 days a 10-year plan cannot be cancelled in-app (it does not renew); the page says "contact support". Say if you want a different rule.
