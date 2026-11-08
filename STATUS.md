# STATUS
Updated: 2026-11-08 13:45 (Europe/London)    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: see git log
State: IN PROGRESS

## Last completed
- T17.3 — Support mode (impersonation) (Opus). Tenant banner, support cookie, audit. Migration 0050.
- T17.2 — Overview metrics, companies and users search (Haiku). API only.
- T17.1 — Platform admin auth and admin host routing (Haiku).

## Current task
- T17.4 — Subscriptions and refunds, deletion and export queue, contact inbox (S!). API only, as T17.2 and T17.3's API.
  - [ ] 1. Migration 0051: `contact_messages` (global, GRANT like `stripe_events`), platform read on `deletion_requests` and `data_exports`, audit policies for `platform.refund_issued` and `platform.contact_updated`; model + registry + migration test list
  - [ ] 2. `GET /platform/subscriptions` (DB list) and `POST /platform/refunds` (owner only, confirm, reason; Stripe refund via client, key `refund-{payment_intent}`; audited; refused if already refunded)
  - [ ] 3. `GET /platform/deletion-requests` and `GET /platform/data-exports` (queues with status; no code hash)
  - [ ] 4. `GET /platform/contact-messages` and `PATCH /platform/contact-messages/{id}` (mark handled, audited)
  - [ ] 5. Tests `api/tests/db/test_platform_billing.py`; OpenAPI + web `gen:api`; ruff/mypy; related suites; PROGRESS + micro_plan tick; handover
- Resume note: start at step 1. Models of reference: `api/app/modules/billing/`, `api/app/modules/platform_admin/`, migrations `0049`, `0050`.

## Next tasks
- T17.5 (S), T17.6 (S), P17 gate, AUDIT-3.
- leftover.md L1 (Stripe E2E) when the owner has test keys; before Phase 23.

## Health
- CI on dev: green (PR 25 merged, P16). No PR until the P17 gate.
- Local checks: not yet run for T17.4.

## Issues / suggestions
- T17.3 support mode has no admin-side screen yet (see T17.2 note below).
- **Admin pages are unreachable since T17.1.** Nothing in the web calls `POST /auth/platform-session`. Needs an owner call or its own task before any admin screen is shown.
- The admin screens for T17.2 to T17.4 are not built: the steps are API-only.
- (T16.6) The breadcrumb reads "Company / Company" on delete-account (cosmetic).
- (T16.3) Stripe API version not pinned; verify the invoice payment-intent field in test mode (leftover.md L1).
- (T16.2) A lapsed annual plan still says "annual" in /auth/me.

## Strategy / decisions taken
- (T17.2) Routes use the `/platform` prefix that T15.7 set, not the spec's `/admin`.
- (T17.3) Support mode uses its own cookie; one live session per admin; writes on are owner-only and need `confirm: true`.
- (T17.4) Admin refund = one full refund of the latest payment behind a subscription row (annual: the latest invoice's payment; 10-year: its payment intent). It reuses the self-serve idempotency key `refund-{payment_intent}`, so the two paths can never refund the same payment twice. It records `refunded_at` and audits; plan changes follow the existing `charge.refunded` webhook, as for a dashboard refund. No admin "cancel now" for annual in this task.
- (T17.4) The subscriptions list reads the DB only (no live Stripe calls per row); it shows the Stripe ids for lookup.
- (T17.4) `contact_messages` is global (no company), granted like `stripe_events` (0044 convention). Only platform code reads it. The public `POST /public/contact` is T18.1 and is not built here.

## Owner actions needed
- Decide how a comp works for an annual or a free company (the 10-year comp is built). Options: extend Stripe's period for an annual plan; or grant a 10-year plan with no Stripe record. Until then the admin gets 409 COMP_NOT_AVAILABLE.
- Confirm owner-only for mark for deletion and refunds (built) or let any platform admin do it.
- Decide how the platform session starts in the admin UI (see Issues). Admin pages stay unreachable until this is decided.
