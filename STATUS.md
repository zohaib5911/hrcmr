# STATUS
Updated: 2026-11-08 10:50 (Europe/London)    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: see git log

State: IN PROGRESS — T17.2 (S) overview metrics, companies, users search

## Last completed
- T17.1 — Platform admin auth and admin host routing (Haiku). Platform cookie `brand_platform_session`, issued by `POST /api/v1/auth/platform-session` after MFA and inside `ADMIN_IP_ALLOWLIST`; tenant session refused on admin routes, platform token refused on tenant routes; every platform request audited as `platform.access` (migration 0048); red `PlatformBar` on every admin page.
- P16 — Phase 16 gate: PR #25 (dev → main) merged, all checks green. Stripe E2E parked in leftover.md L1.
- T16.6 — Deletion code e-mail sent after commit through the app mailer (Opus).

## Current task
- T17.2 — Overview metrics, companies, users search (micro_plan L394; spec plan.md L1160–1164, L1168, L1465)
  - [ ] 1 metrics endpoint (overview: signups, active companies, paid vs free, MRR estimate, churn, refunds)
  - [ ] 2 companies list (search/filter: plan, status, created, last active) + detail
  - [ ] 3 company actions: suspend/reactivate (reason), extend plan (comp), mark for deletion; all audited
  - [ ] 4 users search by email + lock/unlock; all audited
  - [ ] 5 tests run (affected only), tick micro_plan + PROGRESS, final commit `feat(admin): ... (T17.2)`
- Resume note: start at sub-step 1. Platform guard is `api/app/modules/rbac/platform.py` `require_platform(permission)`: it refuses any permission not in its allowlist (only `platform.content.write`, `platform.rules.publish` today), so new permissions need a policy line there. Routers are mounted in `api/app/main.py`. Permissions already exist in `api/app/core/rbac_matrix.py` PLATFORM_PERMISSIONS.

## Next tasks
- T17.3 (B) support mode (impersonation), after T17.2
- leftover.md L1 (Stripe E2E) when the owner has test keys; before Phase 23.

## Health
- CI on dev: not run for T17.2 yet. Last merge to main: PR #25 (P16), all checks green.
- Local checks run for T17.2: none yet.

## Issues / suggestions
- Running a mixed subset of root-level and DB tests in one pytest call can give "fixture 'database' not found" (pre-existing). The full suite does not show it. Use the full suite as the check, or run DB files separately.
- The platform guard commits its audit row before the handler runs, so a page view is kept even if the handler fails.
- (T16.6) The breadcrumb reads "Company / Company" on delete-account (cosmetic).
- (T16.3) Stripe API version not pinned; verify the invoice payment-intent field in test mode (leftover.md L1).
- (T16.2) A lapsed annual plan still says "annual" in /auth/me.

## Strategy / decisions taken
- (T17.1) Endpoint at `/api/v1/auth/platform-session`; the RBAC rule only exempts `/auth/` from needing a permission dependency.
- (T17.1) Platform session lifetime 8 hours absolute, idle timeout as the store's 8 hours. Issued only after MFA; the IP allowlist is checked at issuance and on every platform request.
- (T17.1) No web sign-in for the platform session yet: T17.2 adds the step on the first admin page that calls the API.
- (T16.6) Only `deletion_code` moved to the app mailer (sent after commit); the other three deletion notices stay as outbox rows.

## Owner actions needed
- None blocking. Stripe test keys go in `.env` when available (names in leftover.md L1); not blocking.
