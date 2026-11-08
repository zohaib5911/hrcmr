# STATUS
Updated: 2026-11-08 14:30 (Europe/London)    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: see git log
State: IN PROGRESS

## Last completed
- T17.4 — Subscriptions and refunds (owner, Stripe client, idempotent, audited), deletion and export queues, contact inbox (Haiku). Migration 0051. Tests: tests/db/test_platform_billing.py 15 pass.
- T17.3 — Support mode (impersonation) (Opus). Tenant banner, support cookie, audit. Migration 0050.
- T17.2 — Overview metrics, companies and users search (Haiku). API only.
- T17.1 — Platform admin auth and admin host routing (Haiku).

## Current task
- T17.5 — Content tools and feature flags (S). Not started at this commit.
- Resume note: read plan L1170, L1175, L1468 and the existing learning/courses and terms modules before writing.

## Next tasks
- T17.5 (S), T17.6 (S), P17 gate (R7, PR dev -> main), AUDIT-3 (stop, big model).
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
