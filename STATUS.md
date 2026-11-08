# STATUS
Updated: 2026-11-08 17:30 (Europe/London)    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: see git log
State: IN PROGRESS — the owner's five questions are answered and built (see Strategy). Next: the P17 gate (R7), which the owner has not yet asked for.

## Last completed
- T17.6 — Jobs dashboard, platform audit log, rules screens, retry from an allow-list (Haiku). Register status moved to T20.5. Migrations 0055, 0056.
- T17.5 — Terms publish (owner), feature flags, announcement banners, dossier links and courses reused; templates and guides moved to T19.17 and T19.16 (repo content). Migrations 0052–0054.
- T17.4 — Subscriptions, owner refunds (Stripe client, idempotent, audited), deletion and export queues, contact inbox. Migration 0051.
- T17.3 — Support mode (impersonation) (Opus). Migration 0050.
- T17.2 — Overview metrics, companies and users search (Haiku). API only.
- T17.1 — Platform admin auth and admin host routing (Haiku).
- Owner answers (2026-11-08): comp access (migration 0057), platform session start in the admin frame (web), retry allow-list, templates and guides as repo content, register status to Phase 20.

## Current task
- None in the micro-plan. P17 gate is next: R7 (full API and web suites, screenshots at phase gates, phase summary, PR dev -> main, merge when green).

## Next tasks
- P17 gate (R7), then AUDIT-3 (stop, big model).
- T20.5 (register status and rerun) belongs to Phase 20, after the register ingest T20.1.
- T19.16 (guides, MDX in content/guides) and T19.17 (templates, content/templates with a manifest and a read-only admin list).
- leftover.md L1 (Stripe E2E) when the owner has test keys; before Phase 23.

## Health
- CI on dev: not run since P16 (PR 25, green).
- Local checks, last run: platform admin, session, billing, content, audit log, jobs, comp, migrations, data-model doc, audit, guards, RBAC enforcement, worker: all pass (the last batches: 79 and 58 and 10 and 7 and 3). OpenAPI and architecture pass (run as a separate command). Web unit 802 pass; typecheck, eslint, prettier clean.
- Not run: the full API suite and the web e2e (the phase gate's R7 does that). The admin session start has NOT been checked in a browser with an MFA-enabled admin; it needs one manual check.
- Known test-order issue (not mine): running tests/test_architecture.py or tests/test_openapi.py before tests/db in one pytest command breaks the `database` fixture. Run them as a separate command.

## Issues / suggestions
- The platform admin pages call the API with the platform cookie; if that cookie expires mid-session, the page shows a 404 (notFound) rather than sending the person to start again. Worth handling in the admin frame.
- Route prefixes are mixed: `/platform/*` and the older `/admin/*` (courses, dossier links). Both are platform-guarded. One consistent prefix before the admin screens are built.
- contact_messages has no RLS (global, the 0044 convention). Only platform code reads it.
- The platform audit read policy (0055) shows every company-less platform and system row to platform admins. Intended for the platform staff log.
- Comp access is not shown on the billing page yet (the API returns `comp_until`; the web does not display it).
- Retry runs a job once more under a new id; the job's own arguments are not needed because the five listed jobs take none.
- (T16.6) The breadcrumb reads "Company / Company" on delete-account (cosmetic).
- (T16.3) Stripe API version not pinned; verify the invoice payment-intent field in test mode (leftover.md L1).
- (T16.2) A lapsed annual plan still says "annual" in /auth/me.

## Strategy / decisions taken (owner answers, recorded 2026-11-08; the agent chose them at the owner's request, and the owner can override any of them)
1. Templates: DOCX/PDF files in the repo under `content/templates/`, reviewed in pull requests; the admin lists them (T19.17). No upload.
2. Guides: MDX files in the repo under `content/guides/`, compiled at build time (T19.16). No MDX upload, because MDX runs JSX and an upload would be script injection.
3. Job retry: only the jobs in `app/jobs/rerun.py` (rtw_status_daily, bank_holidays_weekly, cloudflare_ranges_weekly, files_orphans_daily, report_jobs_sweep), which send nothing and keep no arguments. A re-run is queued under `rerun_<name>`, needs a reason, and is audited. Mail-sending jobs (reminders, digests, deletion and export e-mails, the email sweep) and rules_watch are never listed.
4. Register status and rerun: moved to Phase 20 as T20.5.
5. Comp access: `companies.comp_until` (migration 0057) gives free access until its end date for any plan. It is never written by Stripe. The paid count in the metrics excludes it. An active 10-year plan keeps its own end-date extension.
6. Owner-only: refunds, terms publish, mark-for-deletion (as built).
7. Platform session: the admin frame sends a person without the platform cookie to `/session`, which calls POST /auth/platform-session and forwards Set-Cookie. A refusal goes to `/session-required` with the reason. Redirects use public paths, because the proxy refuses `/platform/...` from a browser.
8. Design: `--on-fixed` (white in both themes) is the token for text on the fixed admin red. It replaces `text-white`, which the switched-off Tailwind palette renders as nothing.

## Owner actions needed
- Nothing is blocking. Two checks only: (a) sign in to the admin host as an MFA-enabled platform admin and confirm the session start and the refusal page; (b) say whether to run the P17 gate (R7) now.
