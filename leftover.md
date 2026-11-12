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

### [x] L2 · S · Phase 17 screenshots (completed in C3.1.10, evidence commit 6d66e69)
- **Why parked:** the new admin screens (platform bar, admin landing, session-required, session start) need a signed-in platform admin in the browser. The e2e server has no seed for one (only `/api/v1/e2e/paid-plan`), and no browser test reaches `admin.example.test` (the host-routing spec sends API requests with a Host header). The tenant support and announcement banners need an announcement or a support session, which the same seed makes possible. Everything else in the P17 gate is green (API 1319, web unit 802, web e2e 437).
- **Needs:** an e2e-only route in `api/tests/e2e_server.py`, like `paid-plan`, that makes a signed-in user a platform admin with MFA; a browser host mapping for `admin.example.test` in `web/playwright.config.ts`; then `web/tests/e2e/phase17-screenshots.spec.ts` modelled on `phase16-screenshots.spec.ts`.
- **Update (C3.1.3, 2026-11-09):** the seed (`POST /api/v1/e2e/platform-admin`) and the admin-host mapping are done, and `web/tests/e2e/platform-admin.spec.ts` uses them. The screenshots stay open and go with C3.1.10. The admin host is plain http in these tests, so client JavaScript does not run there (STATUS, Issues); screenshots of server-rendered pages still work.
- **Steps:** capture the session-required page, the platform bar with the admin landing, the announcement banner and the support banner at 390 and 1280 px, light and dark, into `docs/screenshots/phase-17/`; run the spec with `SCREENSHOTS=1`.
- **Done when:** a screenshot exists for each screen at both widths and both schemes, the spec passes with `SCREENSHOTS=1`, and the result is logged in `PROGRESS.md` under Phase 17. No skipped checks.
- **Completed (C3.1.10, 2026-11-12; 6d66e69):** `SCREENSHOTS=1` targeted Playwright run passed all 6 tests (setup, four width/theme combinations, operations pages). All 48 PNGs are in `docs/screenshots/phase-17/`: ten admin screens and announcement/support banners at 390/1280 px, light/dark. Screenshot-only static CSS/font relay handles the local HTTP admin host; production CSP and blocked admin client scripts are unchanged. Results are also recorded in the agent bus (task branches do not edit `PROGRESS.md`).
