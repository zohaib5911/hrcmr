# STATUS
Updated: 2026-11-08 11:20 (Europe/London)    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: see git log

State: BLOCKED — needs big model (T17.3)

## Last completed
- T17.2 — Overview metrics, companies and users search (Haiku). API only, as the micro_plan steps read: `GET /platform/metrics`; `GET /platform/companies` (search, filter, paged) and `/{id}` (profile, people, last platform actions); `suspend`, `reactivate` (reason required), `extend-plan` (10-year plan with an active subscription only), `mark-for-deletion` (owner only; erases nothing); `GET /platform/users?q=`, `lock` and `unlock`. Every change audited under the platform admin (migration 0049). Tests: `tests/db/test_platform_admin.py` 7 pass.
- T17.1 — Platform admin auth and admin host routing (Haiku). Platform cookie `brand_platform_session`, issued by `POST /api/v1/auth/platform-session` after MFA and inside `ADMIN_IP_ALLOWLIST`; red `PlatformBar` on every admin page.
- P16 — Phase 16 gate: PR #25 merged, all checks green. Stripe E2E parked in leftover.md L1.

## Current task
- None. T17.2 is ticked. The next block in micro_plan is T17.3 (B, support mode): needs a big model.

## Next tasks
- T17.3 (B) Support mode (impersonation). Start a big model (Opus / Solo 6.1) and type: Read AGENTS.md and continue.
- Before any admin screen is built: the web platform-session step (Issues below).
- T17.4 (S!) subscriptions, refunds, deletion and export queue, contact inbox.
- leftover.md L1 (Stripe E2E) when the owner has test keys; before Phase 23.

## Health
- CI on dev: not run for T17.2 (no PR; PR waits for the Phase 17 gate). Last merge to main: PR #25 (P16), all checks green.
- Local checks run for T17.2: platform admin tests 7 pass; platform session, rules and network 19 pass; architecture, OpenAPI, RBAC matrix, audit, guards, migrations 73 pass; ruff, mypy (strict, platform_admin + rbac/platform), web typecheck clean; gen:api:check up to date.
- Not run: the full API suite and web e2e (not a phase gate; the rule is affected tests only).

## Issues / suggestions
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
