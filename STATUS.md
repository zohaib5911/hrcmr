# STATUS
Updated: 2026-11-08 15:30 (Europe/London)    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: see git log
State: BLOCKED — owner decision needed (T17.5 templates and guides; T17.6 retry and register status). P17 gate waits on them.

## Last completed
- T17.4 — Subscriptions, owner refunds (Stripe client, idempotent, audited), deletion and export queues, contact inbox (Haiku). Migration 0051. Tests: tests/db/test_platform_billing.py 15 pass.
- T17.3 — Support mode (impersonation) (Opus). Migration 0050.
- T17.2 — Overview metrics, companies and users search (Haiku). API only.
- T17.1 — Platform admin auth and admin host routing (Haiku).

## Current task
- T17.5 — partly done, BLOCKED (see Owner actions 1–2). Built: owner terms publish (migration 0052), feature flags (0053), announcement banners (0054; API and the app banner), dossier links (existing, audited), course editor (existing API, tests pass). Not built: templates, guides (MDX).
- T17.6 — partly done, BLOCKED (see Owner actions 3–4). Built: platform audit log with CSV export (0055), job dashboard (queue depth and failures). Not built: retry, register status (Phase 20).
- Resume note: nothing half-done in the code. Once the owner answers, start with the item they decide. Everything is committed and pushed.

## Next tasks
- After the owner's answers: finish T17.5 (templates, guides), finish T17.6 (retry, register status moves to Phase 20), then P17 gate (R7, PR dev -> main), then AUDIT-3 (stop, big model).
- leftover.md L1 (Stripe E2E) when the owner has test keys; before Phase 23.

## Health
- CI on dev: not run since P16 (PR 25, green). Gate PR waits for P17.
- Local checks for T17.4–T17.6 (last run): platform admin, session, billing, content, audit log, jobs, migrations, audit, guards, RBAC enforcement: 87 pass; platform content and migrations 17 pass; architecture 13 and OpenAPI pass; data-model doc pass; ruff, mypy (app), Semgrep (CI packs) clean at T17.4; web unit components/app 67 pass, typecheck, eslint, prettier clean.
- Known test-order issue (not mine): running tests/test_architecture.py or tests/test_openapi.py before tests/db in one pytest command breaks the `database` fixture. Run them as a separate command; the full suite runs db first and is unaffected.

## Issues / suggestions
- Admin pages are unreachable since T17.1: nothing in the web calls `POST /auth/platform-session`. Needs an owner call or its own task before any admin screen is shown.
- Admin screens for T17.2 to T17.6 are not built: the steps are API-only (as the blocks read). Only the tenant banners (support mode, announcements) have screens.
- Route prefixes are mixed: `/platform/*` (T15.7 onward) and the older `/admin/*` (courses, dossier links, learning admin). Both guarded by platform permissions. Worth one consistent decision before the admin screens are built.
- The platform guard commits its audit row before the handler runs, so a page view is kept even if the handler fails.
- `metrics.overview` loads every active annual and 10-year company to apply `is_entitled`. Fine at this size; switch to SQL when the count grows.
- (T16.6) The breadcrumb reads "Company / Company" on delete-account (cosmetic).
- (T16.3) Stripe API version not pinned; verify the invoice payment-intent field in test mode (leftover.md L1).
- (T16.2) A lapsed annual plan still says "annual" in /auth/me.
- contact_messages has no RLS (global, the 0044 convention). Only platform code reads it; the public POST (T18.1) must not return rows, and an INSERT ... RETURNING needs care.
- The platform audit read policy (0055) shows every company-less platform and system row to platform admins (their own actions, page views and job runs). That is intended for the platform staff log; say so if it should be narrower.

## Strategy / decisions taken
- (T17.4) Admin refund = one full refund of the latest payment behind a purchase (annual: the latest invoice's payment; 10-year: its payment intent), with the self-serve key `refund-{payment_intent}`, so one payment is refunded at most once. Plan changes follow the existing `charge.refunded` webhook. Owner only; confirm and reason required.
- (T17.4) The subscriptions list reads the DB only; no Stripe call per row.
- (T17.5) Terms publish is owner only. A publish is the newest `published_at`; acceptance is per version, so everyone accepts again (existing mechanism, tested).
- (T17.5) Feature flags: any platform admin with content write sets them; keys must match `^[a-z][a-z0-9_]{2,59}$`; a missing flag is off. No flag reads are wired into features yet.
- (T17.5) Announcement banners: regions uk, us, au; live from start to end, or until ended early; the tenant read is `GET /company/announcements` (any role with `company.overview.read`), filtered to the company's region.
- (T17.6) The job dashboard shows failures and queue depth only. The queue depth reads ARQ's `arq:queue` through `app.state.auth.redis`.
- (T17.6) The platform audit log shows the company-less rows (platform admins and system); tenant rows never appear; the export is audited as `platform.audit_exported`.

## Owner actions needed
1. **Templates (T17.5):** where do the Resources templates (job description, offer letters, RTW checklist, new starter checklist; DOCX/PDF) live? Recommended: files under `content/` in the repo, reviewed in PRs (plan L140), with the admin only listing them. Alternative: uploaded in the admin into a platform file store (new global table and storage prefix).
2. **Guides (T17.5):** MDX guides as repo files (recommended, plan L140; reviewed in PRs; the admin lists and previews them) or uploaded in the admin into the database? If uploaded, we need a strict sanitiser (allow-list Markdown, no raw HTML or JSX) and a parser: say which one.
3. **Job retry (T17.6):** a failed job's arguments are never stored, so retry cannot replay it. Recommended: retry only jobs that take no arguments (the scheduled jobs), and refuse the rest with a clear message. Alternative: store argument ids on failure rows (needs a privacy review).
4. **Register status (T17.6):** the sponsor register ingest is Phase 20, after this gate. Recommended: move "register import status and rerun" into Phase 20 and close T17.6 without it.
5. Earlier: decide how a comp works for an annual or free company; confirm owner-only for mark for deletion, refunds and terms publish; decide how the platform session starts in the admin UI (Issue 1).
