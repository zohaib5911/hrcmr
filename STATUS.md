# STATUS
Updated: 2026-11-08 Europe/London    Agent: Claude Code (Opus 5.5, BIG)    Branch: dev    Commit: see git log

State: HANDED OVER — small model next

## Last completed
- T16.5 — Delete account. API (GET/POST deletion-request, confirm with 6-digit code, DELETE withdraw), migration 0047 (deletion_requests + purge-only DELETE gate on history triggers), deletion_executor_hourly purge (Stripe stop, storage, every tenant row, lone users, stub, audit stub, final e-mail), web /company/delete-account. Tests: deletion DB 4 pass; related DB suites and guards pass.
- T16.4 — Data export. POST /companies/me/export (company.export, step-up, one at a time, 202) queues generate_export; the worker writes a zip (README, documents.csv, documents/, tables/<table>.csv for the 68 company-scoped tables plus the company row) to a private file. Secrets, storage keys, IP/user agent, bank account numbers and sort codes are never exported. Link valid 7 days (data_exports.expires_at, migration 0046, RLS). GET /companies/me/exports/{id} (status); GET /companies/me/exports/{id}/download → 302 to a 60-second link (requester's session needed). E-mail data_export_ready. Tests: 3 DB (two tenants, refusals, expiry); guards and worker tests pass.
- T16.3 — Billing page and cancel with refund (POST /billing/cancel; web /company/billing). Billing DB 13 pass; web lint, typecheck, unit 786 pass.
- T16.2 — Entitlements (402 PLAN_REQUIRED gate) and payment-failed grace.
- T16.1 — Stripe integration and webhooks.
- P15 — PR 23 merged to main (all checks green).

## Current task
- none (T16.5 done)
- Resume note: run `bash .agent/next.sh` → P16 gate (S): Recipe R7 + Stripe test-mode E2E.

## Next tasks
- P16 (S) Phase 16 gate: full API suite, e2e incl. billing + delete-account, PR dev → main. Needs owner's Stripe test keys; if missing → BLOCKED with owner action.

## Health
- CI on dev: not watched (no PR open)    CI on main: green (PR #23)
- Local checks run this session: billing DB 13 pass; export DB 3 pass; reports + worker DB pass; guards: data model doc, migrations, RLS, guards 39 pass; openapi, architecture, rbac matrix, body limits 34 pass; web lint, typecheck, unit 786 pass; ruff/mypy clean on touched modules.
- Full API suite NOT run this session (it runs at the phase gate). Full e2e NOT run.

## Issues / suggestions
- (T16.5) Test isolation: tests/db/test_billing.py counts payment_failed mail across the whole outbox, so it fails if test_email.py runs before it (not in normal file order). test_exports.py had the same issue and is now filtered by address.
- (T16.5) No e2e for /company/delete-account yet; add at the P16 gate (start → code from Mailpit → scheduled → withdraw). T22.1 also lists "deletion with withdraw".
- (T16.5) The admin back office deletion queue (T17.4, GET /admin/deletion-requests) can read deletion_requests directly; T17.2 "mark for deletion" should create a confirmed request rather than a new path.
- (T16.4, fixed in T16.5) the data_export_ready e-mail had no sample in seed/email_samples.py (test_email failed); added.
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
- (T16.5) The company stays status 'active' during the 7 days (the access check refuses anything but active, so 'pending_deletion' would lock admins out and stop a withdrawal). It becomes 'deleted' at the purge.
- (T16.5) History triggers: instead of disabling triggers, each was split: UPDATE (and INSERT) unchanged; DELETE skipped only when current_user is app_owner AND app.purge_company_id equals the row's company (set only by app/db/purge.py). The API role has no DELETE grant on those tables anyway.
- (T16.5) Kept after purge: the company row emptied to a stub (id, 'Deleted company', slug deleted-<id>, plan/subscription fields and Stripe ids), subscriptions (payment records), deletion_requests (completed_at; requested_by set null), and one audit event company.deleted. All other audit events of the company are deleted (plan: "minimal audit stub").
- (T16.5) Users: deleted when they belong to no other company and are not platform staff; if anything else still points at one, it is emptied (e-mail deleted-<id>@deleted.invalid, no password/MFA, inactive) instead.
- (T16.5) A live annual subscription is ended in Stripe (retrieve, then cancel_now, no refund) before anything is deleted; if Stripe fails the request stays due and is retried next hour.
- (T16.5) The data model's export_file_id is export_id (the data export asked for with the request), without a foreign key, because exports are purged while the request is kept.
- (T16.5) Code: 6 digits, HMAC (blind_index, scoped to the request id) not plain SHA-256, 15 minutes, 5 wrong tries end it, new code at most once a minute. Only the requester can confirm; any Company Admin can withdraw. Final e-mail goes to the company's active admins.
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
