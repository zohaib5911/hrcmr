# Leftover — work parked because the owner can't supply something yet

Agents: do **not** block on these. Carry on with `micro_plan.md`. Pick an item up only when the owner says the
missing thing now exists (e.g. keys are in `.env`). Every item must be done before Phase 23 (deployment/launch).
Tick an item (`### [x]`) with its commit when done.

### [ ] L1 · S · Stripe test-mode E2E (parked from the P16 gate, 2026-11-08)
- **Why parked:** owner has no Stripe test keys yet. Everything else in the P16 gate is green (API 1254, web unit 786, web e2e 436, screenshots 16/16).
- **Needs:** owner puts Stripe **test** keys in `.env` (copy `.env.example`): `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ANNUAL`, `STRIPE_PRICE_TEN_YEAR` (see `deployment-requirements.txt`). Values never in chat.
- **Steps:** run `stripe listen` for the webhook secret; then test both plans (annual, ten-year), refund within 14 days, cancel, failed payment (grace + `payment_failed` mail), webhook replay (idempotent).
- **Also check (T16.3):** Stripe API version is not pinned — confirm the invoice payment-intent field in test mode.
- **Done when:** all five flows pass against Stripe test mode; result logged in `PROGRESS.md` under Phase 16. No mocked run counts.
