# STATUS
Updated: 2026-11-09 (Europe/London)    Agent: Claude Code (Opus 5.5, BIG)    Branch: dev    Commit: 55153b7
State: IN PROGRESS — AUDIT-3 round 1 (scope audit-pass-2..55153b7)

## Last completed
- P17 gate (R7) — PR #26 dev -> main merged (merge commit 38537c1) after all 12 checks were green on 2ec407e. API full 1319 pass, web unit 802 pass, web e2e 437 pass (200 screenshot-only skipped). Phase 17 summary in PROGRESS.md. Screenshots parked as leftover.md L2.
- T17.6 — Jobs dashboard, platform audit log, rules screens, retry from an allow-list (Haiku). Register status moved to T20.5. Migrations 0055, 0056.
- T17.5 — Terms publish (owner), feature flags, announcement banners, dossier links and courses reused; templates and guides moved to T19.17 and T19.16. Migrations 0052–0054.
- T17.4 — Subscriptions, owner refunds, deletion and export queues, contact inbox. Migration 0051.
- T17.3 — Support mode (impersonation) (Opus). Migration 0050.
- T17.2 — Overview metrics, companies and users search (Haiku). API only.
- T17.1 — Platform admin auth and admin host routing (Haiku).

## Current task
- None. The next block is AUDIT-3 (B, big model only). A small model stops here.
- Resume note: a big model (Opus / Solo 6.1) runs `audit.md` for AUDIT-3 (covers T15.1 → P17), writes the fixes into `changesneeded.md`, then hands back. Start from `bash .agent/next.sh`.

## Next tasks
- AUDIT-3 (big model), then the fixes in `changesneeded.md`, then the next micro_plan block.
- T20.5 (register status and rerun) belongs to Phase 20, after the register ingest T20.1.
- T19.16 (guides, MDX in content/guides) and T19.17 (templates, content/templates with a manifest and a read-only admin list).
- leftover.md L1 (Stripe E2E) when the owner has test keys; before Phase 23. leftover.md L2 (admin screenshots) needs a platform-admin e2e seed.

## Health
- CI on dev: green (PR #26, 12/12 checks on 2ec407e). CI on main: PR checks were green before the merge; the run on 38537c1 was not checked.
- Local checks: nothing run this session (merge only). Last local runs are the P17 gate's: API full 1319 pass, web unit 802 pass, web e2e 437 pass.
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
3. Job retry: only the jobs in `app/jobs/rerun.py` (rtw_status_daily, bank_holidays_weekly, cloudflare_ranges_weekly, files_orphans_daily, report_jobs_sweep), which send nothing and keep no arguments. A re-run is queued under `rerun_<name>`, needs a reason, and is audited. Mail-sending jobs and rules_watch are never listed.
4. Register status and rerun: moved to Phase 20 as T20.5.
5. Comp access: `companies.comp_until` (migration 0057) gives free access until its end date for any plan. It is never written by Stripe. The paid count in the metrics excludes it. An active 10-year plan keeps its own end-date extension.
6. Owner-only: refunds, terms publish, mark-for-deletion (as built).
7. Platform session: the admin frame sends a person without the platform cookie to `/session`, which calls POST /auth/platform-session and forwards Set-Cookie. A refusal goes to `/session-required` with the reason. Redirects use public paths, because the proxy refuses `/platform/...` from a browser.
8. Design: `--on-fixed` (white in both themes) is the token for text on the fixed admin red. It replaces `text-white`, which the switched-off Tailwind palette renders as nothing.
9. Gate merge: the owner asked for PR #26 to be merged when green; it was merged with `gh pr merge 26 --merge --auto` after all checks passed. dev was fast-forwarded to main (38537c1).

## Owner actions needed
- Manual check (not blocking): sign in to the admin host as an MFA-enabled platform admin and confirm the session start and the refusal page.
- Before Phase 23: leftover.md L1 (Stripe test keys) and L2 (admin screenshots seed).
