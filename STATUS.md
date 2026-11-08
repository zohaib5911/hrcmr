# STATUS
Updated: 2026-11-08 10:45 (Europe/London)    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: see git log

State: HANDED OVER — small model next (T17.2)

## Last completed
- T17.1 — Platform admin auth and admin host routing (Haiku). Platform cookie `brand_platform_session`, issued by `POST /api/v1/auth/platform-session` after MFA and inside `ADMIN_IP_ALLOWLIST`; tenant session refused on admin routes, platform token refused on tenant routes; every platform request audited as `platform.access` (migration 0048); red `PlatformBar` on every admin page.
- P16 — Phase 16 gate: PR #25 (dev → main) merged, all checks green. Stripe E2E parked in leftover.md L1.
- T16.6 — Deletion code e-mail sent after commit through the app mailer (Opus).
- T16.5 — Delete account (Opus).
- T16.4 — Data export.
- T16.3 — Billing page and cancel with refund.
- T16.2 — Entitlements and payment-failed grace.
- T16.1 — Stripe integration and webhooks.

## Current task
- None. Stopped after T17.1 at the owner's request ("start the next one").

## Next tasks
- T17.2 (S) Overview metrics, companies, users search (micro_plan). Admin pages do not call the API yet; the first one that does needs the platform session step (`POST /api/v1/auth/platform-session`) from a signed-in platform admin.
- leftover.md L1 (Stripe E2E) when the owner has test keys; before Phase 23.

## Health
- CI on dev: not run for T17.1 (no PR open). Last merge to main: PR #25 (P16), all checks green.
- CI on main: green at PR #25.
- Open Dependabot PRs #24 (uv) and #5 (npm): not part of this work.
- Local checks run for T17.1: full API suite 1270 passed (exit 0); web lint 0 warnings, typecheck clean, unit (platform-bar) pass; host-routing e2e 13 pass; guard suites 205 pass.

## Issues / suggestions
- Running a mixed subset of root-level and DB tests in one pytest call can give "fixture 'database' not found" (pre-existing; seen again with the new DB test file). The full suite does not show it. Use the full suite as the check, or run DB files separately.
- The platform guard commits its audit row before the handler runs, so a page view is kept even if the handler fails. Failed actions therefore leave a `platform.access` row, not an action row.
- The platform session has no column in `sessions`; its audit trail is the `platform.session.started`/`ended` events and the `platform.access` rows.
- (T16.6) The breadcrumb reads "Company / Company" on delete-account (cosmetic).
- (T16.6) `deletion_scheduled`(+support), `deletion_withdrawn`, `account_deleted` still use the outbox helper (minute sweep).
- (T16.3) Stripe API version not pinned; verify the invoice payment-intent field in test mode (leftover.md L1).
- (T16.2) A lapsed annual plan still says "annual" in /auth/me.

## Strategy / decisions taken
- (T17.1) Endpoint at `/api/v1/auth/platform-session`: the RBAC rule only exempts `/auth/`, `/health`, `/ready`, `/public/`, `/webhooks/` from needing a permission dependency, and session management belongs with auth. The router file lives in `rbac/` because it reuses the platform guard helpers.
- (T17.1) Tenant session on the admin routes → 403 FORBIDDEN (a signed-in non-admin always got 403 there); no session at all → 401. A token of the wrong kind is refused whichever cookie carries it.
- (T17.1) Platform session lifetime 8 hours absolute (tenant session 14 days), idle timeout as the store's 8 hours. Issued only after MFA; the IP allowlist (`ADMIN_IP_ALLOWLIST`, already in the settings and env docs) is checked at issuance and on every platform request. Unparseable allowlist entries match nothing.
- (T17.1) Audit inserts for platform admins need per-action RLS policies (as 0019, 0035 and 0043 did). Migration 0048 adds `platform.access`, `platform.session.started`, `platform.session.ended`.
- (T17.1) No web sign-in for the platform session yet: the admin pages call no API at this point. T17.2 will need the step, and it goes in that task.
- (T16.6) Only `deletion_code` moved to the app mailer (sent after commit); the other three deletion notices stay as outbox rows in the same transaction.
- (P16) Stripe E2E stays parked in leftover.md L1; no mocked run counts as the test-mode E2E.

## Owner actions needed
- None blocking. Stripe test keys go in `.env` when available (names in leftover.md L1); not blocking.
- Confirm (from T16.3/T16.4): 10-year plans cannot be cancelled in-app after 14 days; bank numbers and sort codes are left out of the export; the export e-mail link needs a signed-in session.
