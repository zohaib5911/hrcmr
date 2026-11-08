# STATUS
Updated: 2026-11-08 Europe/London    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: see git log

State: BLOCKED — needs big model (T16.5)

## Last completed
- T16.4 — Data export. POST /companies/me/export (company.export, step-up, one at a time, 202) queues generate_export; the worker writes a zip (README, documents.csv, documents/, tables/<table>.csv for the 68 company-scoped tables plus the company row) to a private file. Secrets, storage keys, IP/user agent, bank account numbers and sort codes are never exported. Link valid 7 days (data_exports.expires_at, migration 0046, RLS). GET /companies/me/exports/{id} (status); GET /companies/me/exports/{id}/download → 302 to a 60-second link (requester's session needed). E-mail data_export_ready. Tests: 3 DB (two tenants, refusals, expiry); guards and worker tests pass.
- T16.3 — Billing page and cancel with refund (POST /billing/cancel; web /company/billing). Billing DB 13 pass; web lint, typecheck, unit 786 pass.
- T16.2 — Entitlements (402 PLAN_REQUIRED gate) and payment-failed grace.
- T16.1 — Stripe integration and webhooks.
- P15 — PR 23 merged to main (all checks green).

## Current task
- T16.5 — Delete account (B). Not started. Big model only (purge executor deletes tenant data). Read micro_plan T16.5 and plan.md L1091–1096, L1460, API item 22 (`POST /companies/me/deletion-request`, `.../confirm`, `DELETE .../deletion-request`).
- Resume note: nothing written for T16.5. The deletion_requests table (plan 6.x L612) and the `deletion_executor_hourly` cron (scheduled.py, currently _nothing_yet) are the starting points. The export from T16.4 (`export_requested`, `export_file_id`) is the offer-an-export step.

## Next tasks
- T16.5 (B), then the Phase 16 gate (full API suite, e2e for both plans, PR dev → main)

## Health
- CI on dev: not watched (no PR open)    CI on main: green (PR #23)
- Local checks run this session: billing DB 13 pass; export DB 3 pass; reports + worker DB pass; guards: data model doc, migrations, RLS, guards 39 pass; openapi, architecture, rbac matrix, body limits 34 pass; web lint, typecheck, unit 786 pass; ruff/mypy clean on touched modules.
- Full API suite NOT run this session (it runs at the phase gate). Full e2e NOT run.

## Issues / suggestions
- (test harness, pre-existing) Running `tests/test_openapi.py` in the same pytest call as `tests/db/test_reports.py` (plus test_migrations or test_data_model_doc) gives "fixture 'database' not found" for every DB test. Reproduced with the untouched test_reports.py, so it predates T16.4. Run those in separate calls, or fix the conftest module-name clash (tests/db/conftest.py vs the root conftest.py).
- (T16.4) There is no web page for exports. The e-mail link opens the API download (needs the requester's signed-in session). The company nav has no Data export item yet; the page belongs with the account lifecycle UI.
- (T16.4) Users (global table) are not exported; the export has memberships (user ids) only. Names and e-mails of staff are in the employees table, not in users.
- (T16.4) The whole archive is built in one worker run and one table is read at a time into memory. Large companies may need a streamed version.
- (T16.3) Stripe's API version is not pinned: the invoice payment intent is read from `payment_intent` or from `payments`. Verify in Stripe test mode at the phase gate.
- (T16.3) Stripe only keys POST for idempotency; the immediate cancel (DELETE) has no key. Safe because the endpoint reads the subscription first and skips the cancel once it has ended.
- (T16.3) The billing page has no e2e spec yet (it was checked by a temporary render test, deleted). Add one at the P16 gate.
- (T16.3) Prices in the page copy (£50 a year, £240 once) are text. Keep them in step with the Stripe price ids.
- (T16.2) A lapsed annual plan (past_due after grace) still says "annual" in /auth/me. The billing page shows the grace state.
- (T16.2) Test companies (raw inserts in tests/db) are on annual/active. A free-plan test must set plan = 'free' itself.
- OpenAPI component names must be unique. After any new endpoint run `pnpm gen:api` in web and check no names disappear. Operation ids use `tag_name`: tags must not contain spaces (use `account-lifecycle`).
- Body limits: every upload route must be in the limits table in api/app/main.py.
- Architecture rule: app code may not use any `.text` attribute (it is taken for raw SQL text()).

## Strategy / decisions taken
- (T16.4) The e-mail link is the API download address, not a bearer link to storage. It needs the requester's session, and the link works for 7 days (data_exports.expires_at). A bearer link would give the zip to anyone who got the e-mail.
- (T16.4) Excluded: the `sessions` table; columns token_hash, share_code, preview_token, storage_key, ip, user_agent, request_id, impersonation_session_id, step_up_at, mfa_passed_at, account_number, sort_code, ni_number_index. Owner should confirm bank numbers are left out (the company can see them in the app).
- (T16.4) Documents: every clean file except the app's own outputs (owner_type report_result or data_export). A document that cannot be read is listed as missing, not dropped silently.
- (T16.4) Only company.export (company admin) can ask, list, or download. Asking needs step-up; reading the status and downloading do not.
- (T16.3) Within 14 days: refund the first payment (annual: latest invoice's payment intent; 10-year: its payment intent), commit, then cancel the Stripe subscription at once. Refund key `refund-<payment_intent>`. After 14 days (annual): cancel_at_period_end with key `cancel-period-<subscription>`, no refund.
- (T16.3) 10-year after 14 days: no renewal exists, so there is nothing to cancel. The endpoint answers 409 NOTHING_TO_CANCEL. Owner should confirm this reading.
- (T16.3) "Contact support" uses the e-mail address (SUPPORT_EMAIL, else support@<domain>), returned as `support_email` in GET /billing/subscription.
- (T16.3) Choosing a plan is offered only on the free plan. A lapsed annual plan recovers through "Payment details and invoices".
- (T16.3) Audit actions: billing.refunded (refund made) and billing.cancelled (cancel requested), both by the requesting user.
- (T16.2) "profile" in plan 8.16's exemption list is read as the company profile (company.profile.write), so a free company can complete its details before paying.
- (T16.2) Annual entitlement follows Stripe's status, not the stored period end.

## Owner actions needed
- Confirm: after 14 days a 10-year plan cannot be cancelled in-app (it does not renew); the page says "contact support". Say if you want a different rule.
- Confirm: bank account numbers and sort codes are left out of the data export.
- Confirm: the export e-mail link needs a signed-in session (not a bearer link).
