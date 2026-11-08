# STATUS
Updated: 2026-11-08 13:30 (Europe/London)    Agent: Claude Code (Opus 5.5, BIG)    Branch: dev    Commit: see git log
State: HANDED OVER — small model next

## Last completed
- T17.3 — Support mode (impersonation) (Opus). Start with reason + ticket ref → separate `brand_support_session` cookie, 30 min, company seen as `company_admin`, read-only unless an owner turns writes on (own session, `confirm: true`); end from admin side or the tenant banner; company-visible audit `support.session.*` + platform `platform.support_*`. Migration 0050. Tests: `tests/db/test_support_mode.py` 5 pass; banner unit 2 pass.
- T17.2 — Overview metrics, companies and users search (Haiku). API only.
- T17.1 — Platform admin auth and admin host routing (Haiku).

## Current task
- None. T17.3 ticked. Next block T17.4 (S!).

## Next tasks
- T17.4 (S!) subscriptions, refunds, deletion and export queue, contact inbox.
- T17.5 (S), T17.6 (S), P17 gate, AUDIT-3.
- leftover.md L1 (Stripe E2E) when the owner has test keys; before Phase 23.

## Health
- CI on dev: not run (no PR until the P17 gate). Last merge to main: PR #25 (P16), all green.
- Local checks for T17.3: support mode 5 pass; audit, auth endpoints/flows, deletion, exports, guards, migrations, platform admin/session, rules admin, tenant session, RBAC enforcement, OpenAPI, architecture, config, platform network, RBAC matrix: 197 pass; ruff, ruff format, mypy (app, 321 files) clean; web typecheck, lint, prettier clean; shell + banner unit 21 pass; gen:api:check up to date; Semgrep (CI rule packs) clean on migrations 0048-0050 and the support module.

## Issues / suggestions
- T17.3 support mode has no admin-side screen to start it yet (the admin pages still lack the web platform-session step, see below). The API and the tenant banner are done; the start form (reason, ticket ref) and the write toggle with its confirm dialog belong with the admin Companies screens.
- In support mode "Sign out" in the avatar menu gets SUPPORT_READ_ONLY (account routes never write in support mode); the banner's "End support mode" is the way out. Could make the avatar menu end support instead when `me.support` is set.
- **Admin pages are unreachable since T17.1 (found in T17.2).** Nothing in the web calls `POST /auth/platform-session`, so the platform cookie is never set. `web/app/(admin)/platform/rules/page.tsx` and `.../courses/page.tsx` call `/platform/*` through `serverApi()` with only the tenant cookie, get 403, and `notFound()` runs. The step (a button in the admin frame that starts the session, and what to show when MFA is missing) is a UI decision; it is not in the T17.2 steps, so it is not built. Needs an owner call or its own task before any admin screen is shown.
- The admin screens for T17.2 (Overview, Companies list and detail, Users) are not built: the steps are API-only. Decide whether they belong in T17.2 or in a follow-up.
- Not in T17.2 (spec 8.18, plan L1640): overview error rate, job queue health and register freshness (these come with T17.6); company detail notes and users reset MFA / resend verification (`/notes`, `/users/{id}/reset-mfa`); company storage used.
- The platform guard commits its audit row before the handler runs, so a page view is kept even if the handler fails. Failed actions therefore leave a `platform.access` row, and no action row.
- `metrics.overview` loads every active annual and 10-year company to apply `is_entitled`. Fine at this size; switch to SQL when the count grows.
- The T17.2 suspend and lock actions take effect at once: the tenant request path already refuses a non-active company (`ACCOUNT_SUSPENDED`) and a deactivated user (`_caller`).
- (T16.6) The breadcrumb reads "Company / Company" on delete-account (cosmetic).
- (T16.3) Stripe API version not pinned; verify the invoice payment-intent field in test mode (leftover.md L1).
- (T16.2) A lapsed annual plan still says "annual" in /auth/me.

## Strategy / decisions taken
- T17.3: support mode uses its own cookie (`SUPPORT_SESSION_COOKIE_NAME`, default `brand_support_session`) so the admin's own tenant session is untouched and returns when support ends. While it is live it wins on every tenant route.
- T17.3: the support view is role `company_admin` with no employee record; writes are blocked in `require()` until turned on. Only the owner who started the session can turn writes on (simplest safe reading of "owner level + second confirmation"; the confirmation is `confirm: true`, the UI's dialog). Anyone platform-level may end any session or turn writes off.
- T17.3: one live support session per admin; starting another ends the previous. Support starts only on an active company. A stale support cookie is ignored for reads (own session takes over) but refuses writes with SUPPORT_SESSION_ENDED.
- T17.3: tenant reads in support mode are not audited one by one (the start entry with reason and ticket is the company-visible record; changes are audited as usual with `impersonation_session_id`).
- (T17.2) Routes use the `/platform` prefix that T15.7 set (`/platform/rules`), not the spec's `/admin`.
- (T17.2) Lock = `users.is_active` false, the existing "account is off" flag (sign-in and every session refuse it). Unlock sets it back. A platform admin cannot lock their own account (409 SELF_LOCK).
- (T17.2) Any platform admin (support or owner) may read, suspend, reactivate, extend and lock. Mark for deletion is owner only, checked in the handler: the spec does not say, and it is the most destructive action here.
- (T17.2) Mark for deletion sets `companies.status = pending_deletion` and nothing else. The purge stays tied to the company's own confirmed deletion request (T16.5), so one click erases nothing.
- (T17.2) Extend the access end date only for a 10-year plan with `subscription_status = active` (the entitlement reads that date). Refused for annual (access follows Stripe) and for free (no plan to extend). Both are open questions for the owner (below).
- (T17.2) MRR and ARR estimate use £50 a year (plan.md L51) as a constant in `metrics.py`; the 10-year plan adds nothing to MRR. Churn = paid plans whose end date fell in the last 30 days. Refunds = a count of `subscriptions.refunded_at` in 30 days.
- (T17.2) Migration 0049: platform read on `memberships` and `subscriptions` (tenant tables), and insert and read on `audit_events` for the six actions with no company, as earlier migrations did. `companies` and `users` have no RLS, so no policy was needed for them.
- (T17.2) Every platform action row has `company_id` NULL, `entity_type` `company` or `user`, and `entity_id` set; the reason is stored in `audit_events.reason`.

## Owner actions needed
- Decide how a comp works for an annual or a free company (the 10-year comp is built). Options: extend Stripe's period for an annual plan; or grant a 10-year plan with no Stripe record. Until then the admin gets 409 COMP_NOT_AVAILABLE.
- Confirm owner-only for mark for deletion (built) or let any platform admin do it.
- Decide how the platform session starts in the admin UI (see Issues). Admin pages stay unreachable until this is decided.
