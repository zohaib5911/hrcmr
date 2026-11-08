# STATUS
Updated: 2026-11-08 Europe/London    Agent: Claude Code (Opus 5.5, BIG)    Branch: dev    Commit: aa38247
State: IN PROGRESS

## Last completed
- T16.1 — Stripe integration and webhooks: client (api/app/integrations/stripe.py), migration 0044 (subscriptions, stripe_events), billing router (GET subscription, checkout, portal), POST /webhooks/stripe. Tests 13 pure + 6 DB pass.

## Current task
- T16.2 — Entitlements and payment-failed grace (B)
  - [ ] 1. entitlements: is_entitled (annual by status, 10-year by end date, past_due within 7-day grace); 402 PLAN_REQUIRED gate in rbac require() for writes
  - [ ] 2. migration 0045: companies.payment_grace_ends_at; webhook sets it on first invoice.payment_failed, clears it when paid; e-mail + notification to company admins
  - [ ] 3. tests: pure entitlement rules, DB gate + grace; existing test companies made paid (two_companies), e2e helper marks accounts paid
  - [ ] 4. full API suite; affected e2e specs
- Resume note: see .agent/journal.md last line.

## Next tasks
- T16.3 (S!), T16.4 (S!), T16.5 (B), P16

## Health
- CI on dev: PR 23 (Phase 15) re-running after the status push; merges when green    CI on main: green (PR #22)
- Local checks run: billing pure 13 + DB 6; migrations, RBAC enforcement/matrix, openapi, architecture, data-model, RLS, identity, body limits, config pass; ruff/mypy clean; Semgrep (CI rulesets) clean on new files.

## Issues / suggestions
- (T16.1) invoice.payment_failed only syncs the subscription status (past_due) and audits billing.payment_failed. The 7-day grace and e-mails are T16.2's.
- (T16.1) The billing page (T16.3) must use /company/billing: Checkout's success and cancel URLs and the portal return URL point there (?checkout=success|cancelled).
- (T16.1) T16.3 cancel/refund: add cancel_subscription and create_refund to api/app/integrations/stripe.py (same _post with an idempotency key); the webhook already ends a refunded 10-year plan (charge.refunded) and an annual plan on customer.subscription.deleted.
- OpenAPI component names must be unique. Pydantic qualifies a clashing name, which drops the original from web/lib/api/schema.ts. SOC models use the Soc prefix (SocCandidateOut, SocCvMatchOut, ...). After any new endpoint run `pnpm gen:api` in web and check that no names disappear.
- Body limits: every upload route must be in the limits table in api/app/main.py. The SOC CV route is there (PROOF_LIMIT). tests/test_body_limits.py enforces it.
- Architecture rule: app code may not use any `.text` attribute (it is taken for raw SQL text()). Use itertext() or other names (the stripping result field is `cleaned`).
- Test harness: the rig's `two_companies` runs `truncate users, companies cascade`, which also truncates rules_versions (rows refer to users). Tests that need published rules publish them after the rig (tests/db/test_soc_match.py).
- Test harness: temporary_database() re-provisions app_owner/app_user; do not run DB suites in parallel.
- pypdf is now a runtime dependency (moved from dev). types-defusedxml is a dev stub.
- CV stripping is pattern based. It does not remove names (the plan does not ask for it), and a street address with no street type word is not caught. The redaction layer in app/ai still runs on the request body.
- CV match does not suggest other SOC codes ("Code 3544 fits better"). That would need the search retrieval on the job title; not done in T15.5.
- The CV match response has no rules version (the disclaimer in T15.6 must show rules version and date from the checker).
- PROGRESS.md ends with an old unchecked Phase 15 list (T15.2–T15.7). The [x] lines above it are the record.
- AI ranking gating: ai_ready only. ai.ask.use is in the matrix but no code checks it (same as letters).
- Job descriptions with personal data are redacted before the call, not refused (only a body with restricted data left after redaction gets AI_REFUSED).
- Pre-existing: OpenAPI already had five qualified AddressOut names (app__modules__companies__..., app__modules__employees__personal_schemas__...). Not from SOC.

## Strategy / decisions taken
- (T16.1) Stripe is called with httpx (no stripe SDK), like the other integrations; tests swap the transport. No Stripe-Version is pinned; the webhook reads both the old and the 2025 shapes (period on items, invoice subscription under parent).
- (T16.1) The webhook finds the company from metadata.company_id (set on the Checkout session, the subscription and the payment intent), else from the Stripe customer's metadata, then scopes the transaction to it. If the company already holds a different customer id, the event is ignored.
- (T16.1) Subscription events re-read the live subscription from Stripe, so out-of-order delivery cannot roll the state back. An event id is stored in the same transaction as its change; a Stripe outage while applying returns 502 and nothing is stored, so Stripe's retry applies it.
- (T16.1) A 10-year plan runs from the event time (paid) for 10 calendar years; the cooling-off end is start + 14 days for both plans. Checkout is refused (409 PLAN_ALREADY_ACTIVE) while a plan is live; plan changes go through support (plan 8.16).
- (T16.1) The customer id is committed as soon as it is made, so a failed Checkout call never leads to a second customer.
- (T15.4) Search needs soc.check.read; match needs soc.check.run (auditors can search, not match). Retrieval: 30 hits per leg (trigram, FTS, vector on index titles, vector on unit groups), fused by reciprocal rank (k = 60), top 10. Re-rank: fast=False (ANTHROPIC_MODEL_MAIN), 1,500 max tokens, strict JSON (unique candidate codes). Any unusable reply, AI error or rate limit: search order with notice, ai_ranked false.
- (T15.4) The plan's "JSON schema" is enforced by pydantic on the reply, not by an API schema feature.
- (T15.4) Response `checks` = engine CheckResult. Decimal values serialise as strings (pydantic v2 default).
- (T15.4) The embedder loads on first use (fastembed in a thread) and is kept on app.state.soc_embedder; tests set a fake there. A failure gives 503 SOC_SEARCH_UNAVAILABLE.
- (T15.5) Endpoint order: AI on (409), size (10 MB, 413), empty (422), PDF or DOCX by name (422), magic bytes (415), virus scan through app.state.files.scanner (422 infected, 503 scan down), readable text (422), SOC code exists (404), Claude (502 if the reply is unusable: no fallback, the feature is AI-only). The CV is held in memory only; nothing is stored.
- (T15.5) Quotes: every evidence quote must appear in the cleaned CV (case and spacing folded). Quotes that do not are dropped, not shown.
- (T15.5) Phone rule: a leading + with 8-13 digits, or a UK national number of 10-11 digits starting 0. A 12-digit CV date range is not treated as a phone number.
- (T15.5) Street rule: a house number, up to three capitalised words, then a street type on the same line. green, row and view are left out.

## Owner actions needed
- None for T15.5. Reminder: the AI features need ANTHROPIC_API_KEY (the CV match is hidden without it).
