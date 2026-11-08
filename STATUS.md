# STATUS
Updated: 2026-11-08 01:34 Europe/London    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: 88808f9

State: IN PROGRESS

## Last completed
- T16.2 — Entitlements (402 PLAN_REQUIRED gate in rbac require(), app/modules/billing/entitlements.py) and payment-failed grace (7 days, admin e-mail + notification). Full API 1242 pass; full e2e 433 pass (184 skipped).
- T16.1 — Stripe integration and webhooks (api/app/integrations/stripe.py, app/modules/billing/).
- P15 — PR 23 merged to main (all checks green).

## Current task
- T16.3 — Billing page, cancel with refund (S!). Started by a small model (Haiku).
  - [ ] 1. Stripe client: retrieve_invoice, create_refund (idempotency key), cancel_subscription_now, cancel_at_period_end
  - [ ] 2. POST /billing/cancel (service + router): within 14 days = full refund + cancel now; after = cancel at period end; 10-year after 14 days = 409; GET /billing/subscription adds payment_grace_ends_at
  - [ ] 3. DB tests (mocked Stripe): day 13 vs day 15, refund idempotency key, audit event
  - [ ] 4. Web: /company/billing page (plan card, 14-day banner, Cancel, portal, contact support, plan choice on free); regen API schema, check no names lost
  - [ ] 5. Lint/typecheck/tests for the areas touched; tick micro_plan + PROGRESS; final commit
- Resume note: nothing written yet. Read api/app/integrations/stripe.py, api/app/modules/billing/service.py, api/tests/db/test_billing.py (FakeStripe) before editing. Verify with `cd api && pytest tests/db/test_billing.py` (see api/ README for the DB setup) and `cd web && pnpm typecheck && pnpm lint`.

## Next tasks
- T16.4 (S!), T16.5 (B), P16

## Health
- CI on dev: not watched (no PR open)    CI on main: green (PR #23)
- Local checks run: none yet for T16.3.

## Issues / suggestions
- (T16.2) Test companies (raw inserts in tests/db) are on annual/active. A free-plan test must set plan = 'free' itself (see tests/db/test_billing.py fixture `free`).
- (T16.2) /auth/me shows `plan` only. A lapsed annual plan (past_due after grace) still says "annual", so the free-plan banner does not show; the 402 upgrade sheet does. T16.3's billing page shows the status and grace end.
- (T16.1) The billing page must use /company/billing: Checkout's success and cancel URLs and the portal return URL point there (?checkout=success|cancelled).
- OpenAPI component names must be unique. Pydantic qualifies a clashing name, which drops the original from web/lib/api/schema.ts. After any new endpoint run `pnpm gen:api` in web and check that no names disappear.
- Body limits: every upload route must be in the limits table in api/app/main.py.
- Architecture rule: app code may not use any `.text` attribute (it is taken for raw SQL text()).
- Test harness: the rig's `two_companies` truncates users and companies cascade. Do not run DB suites in parallel.
- AI ranking gating: ai_ready only. ai.ask.use is in the matrix but no code checks it.
- Pre-existing: OpenAPI already had five qualified AddressOut names. Not from SOC.

## Strategy / decisions taken
- (T16.3) Within 14 days: refund the first payment through Refunds (annual: the latest invoice's payment intent; 10-year: its payment intent), then cancel the Stripe subscription at once (DELETE, no idempotency key since Stripe only keys POST). Refund key is `refund-<payment_intent>`, so a retry cannot refund twice.
- (T16.3) After 14 days (annual): POST subscription with cancel_at_period_end=true, key `cancel-period-<sub>`, then sync from Stripe.
- (T16.3) 10-year after 14 days: no renewal exists, so there is nothing to cancel; the endpoint answers 409 NOTHING_TO_CANCEL and the page says to contact support. Owner should confirm this reading.
- (T16.2) "profile" in plan 8.16's exemption list is read as the company profile (company.profile.write), so a free company can complete its details before paying. /auth (own account) is never gated.
- (T16.2) Annual entitlement follows Stripe's status, not the stored period end; past_due with no grace date yet counts as within grace.
- (T16.1) Stripe is called with httpx (no stripe SDK). Tests swap the transport.
- (T16.1) Subscription events re-read the live subscription from Stripe, so out-of-order delivery cannot roll the state back.

## Owner actions needed
- None for T16.3 yet. Question for owner: after 14 days, a 10-year plan cannot be cancelled in-app (it does not renew); confirm, or say what to do instead.
