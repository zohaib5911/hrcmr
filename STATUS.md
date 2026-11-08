# STATUS
Updated: 2026-11-09 01:50 (Europe/London)    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: see git log
State: BLOCKED — needs big model (C3.1.4): e2e admin-host decision (see Issues). AUDIT-3 fixes 9 of 16 done.

## Last completed
- C3.1.11 — billing page: Export all your data card, step-up sheet, 409 message (625dd58). Web unit 808 pass.
- C3.1.15 — --fixed-admin token replaces raw #b00010 (c177fd7). Web unit 806 pass at that point.
- C3.1.14 — billing page shows complimentary access until comp_until (5bd8b10). 2 tests.
- C3.1.13 — rules watch fetches only PAGE_URLS; stored URLs compared first (c8b1719). rules_watch 4 pass.
- C3.1.16 — code_hash not exported; export test checks every table header (c2f474d). exports 3 pass.
- C3.1.12 — support admin cannot lock a platform admin (1c72492). platform_admin 8 pass.
- C3.1.3 — e2e platform-admin seed + admin-host mapping; platform-admin e2e 5 pass (e2b9e7b).
- C3.1.2 — platform session start moved to the browser (8f4ca0e). host-routing e2e 14 pass.
- C3.1.1 — 10-year platform refund ends the company's plan (e4f21f8). billing tests 29 pass.
- AUDIT-3 round 1 (Opus) — 0 P0 / 10 P1 / 6 P2 (changesneeded.md).

## Current task
- AUDIT-3 fixes — changesneeded.md. Done: C3.1.1, 2, 3, 11, 12, 13, 14, 15, 16. Open: C3.1.4 to C3.1.10 (admin screens, all P1).
  - [ ] C3.1.4 landing metrics — BLOCKED (the e2e question below)
  - [ ] C3.1.5 companies, C3.1.6 users, C3.1.7 subscriptions, C3.1.8 queues and contact, C3.1.9 settings, C3.1.10 jobs and audit + screenshots — all wait for the same decision.
- Resume note: `bash .agent/next.sh` prints C3.1.4. Do not start it until the owner (or a big model) answers the question below. Each screen item needs a client component (the rules-editor pattern, `attempt()`) and an e2e spec, and the e2e cannot run the client code yet.

## Next tasks
- Decision (below), then C3.1.4 to C3.1.10 in order.
- Then AUDIT-4 (`AUDIT NEEDED`) if the loop asks for it: changesneeded has no P0/P1 left only after C3.1.4 to C3.1.10 are done.
- T19.16 (guides), T19.17 (templates), T20.5 (register and rerun), leftover.md L1 (Stripe keys, before Phase 23).

## Health
- CI on dev: last green at PR #26 (12/12). The audit fixes are not in CI yet (no PR opened).
- Local checks run for this batch:
  - API: tests/db/test_platform_billing.py + test_billing.py 29 pass; test_platform_admin.py 8 pass; test_exports.py 3 pass; test_rules_watch.py 4 pass; ruff, ruff format, mypy clean on touched files; tests/e2e_server.py ruff/mypy clean.
  - Web: unit suite 808 pass (after C3.1.11); lint, typecheck, prettier clean.
  - Web e2e: host-routing 14 pass (after C3.1.2); platform-admin 5 pass (after C3.1.3). Full web e2e not run in this batch.
- Known test-order issue (not mine): running tests/test_architecture.py or tests/test_openapi.py before tests/db in one pytest command breaks the `database` fixture. Run them as a separate command.

## Issues / suggestions
- **E2E admin host runs no client JavaScript (C3.1.3).** The admin host is plain http in the tests. The production CSP adds `upgrade-insecure-requests` (web/lib/security/csp.ts), so the browser upgrades the admin page's `_next` script and CSS requests to https, and they fail (ERR_SSL_PROTOCOL_ERROR). Server-rendered admin pages work (the 5 platform-admin e2e tests pass). Do not drop the directive from production.
- **E2E browser calls from the admin host to the API are cross-site (C3.1.3).** The API is at 127.0.0.1:8100 and the admin host is a different site, so SameSite=Lax session cookies are not sent. In production both are one site. So the admin screens' API calls fail in e2e even if the JS ran.
- The platform admin pages call the API with the platform cookie; an expired cookie shows a 404 (notFound) until C3.1.4 adds the redirect helper.
- Route prefixes are mixed: `/platform/*` and the older `/admin/*` (courses, dossier links). Both are platform-guarded. One prefix before the admin screens are built.
- contact_messages has no RLS (global, the 0044 convention). Only platform code reads it.
- The platform audit read policy (0055) shows every company-less platform and system row to platform admins. Intended for the platform staff log.
- Retry runs a job once more under a new id; the five listed jobs take no arguments.
- (T16.6) The breadcrumb reads "Company / Company" on delete-account (cosmetic).
- (T16.3) Stripe API version not pinned; verify the invoice payment-intent field in test mode (leftover.md L1).
- (T16.2) A lapsed annual plan still says "annual" in /auth/me.
- The billing page's cancel-at-period-end copy and the comp alert are not covered by an e2e test (unit only).
- The "Admin screens" e2e requirement in changesneeded.md assumes client JS on the admin host. Either the owner accepts unit-only coverage for the client parts and e2e for server-rendered reads, or the e2e setup changes (see the question).

## Strategy / decisions taken
- Fix one changesneeded item per commit, then a `chore(audit)` commit that ticks it with the fix commit's sha.
- C3.1.1: a 10-year refund ends the plan in the same step as `_refunded()` (plan free, status refunded, ends now); annual refunds stay as they are.
- C3.1.2 (replaces owner answer 7's "forwards Set-Cookie"): the session start is made by the browser. `/session` is a server page rendering `components/platform/session-start.tsx`, which calls the API with `createApiClient` (no enrolment redirect, so a refusal reaches `/session-required`). The layout lets `/session` through. The cookie is set on the shared `.<domain>`, so the admin host sees it in production.
- C3.1.3: the e2e seed sets a fixed TOTP secret (JBSWY3DPEHPK3PXP) through the app's own encryption. The helper (`web/tests/support/platform.ts`) copies the platform cookie from the API's answer to the admin host, because the browser start cannot run in e2e (see Issues).
- C3.1.12: a support admin is refused locking another platform admin (owners included). Locking yourself stays SELF_LOCK (the router skips the new check for the caller).
- C3.1.13: the watch refuses a stored address that differs from `PAGE_URLS`, before any request.
- C3.1.14: complimentary access is an info alert above the plan card while `comp_until` is in the future.
- C3.1.15: `--fixed-admin` (#b00010, the same in both themes) in globals.css, `bg-fixed-admin`, the design catalog and the expected tokens.
- C3.1.11: the export card asks for the password through the step-up sheet only when the API says STEP_UP_REQUIRED; a 409 shows the API message.

## Owner actions needed
- **Question for the big model or owner (blocks C3.1.4 to C3.1.10):** how should the e2e tests reach the admin screens?
  1. Keep the production CSP and the cross-site layout, and test the admin screens with unit tests plus e2e for server-rendered pages only. This changes the "Done when" of C3.1.4 to C3.1.10 (no e2e for the client actions). Recommended: no production change.
  2. Serve the e2e admin host over https (a TLS proxy in the Playwright web server), and map an API host in the same site (`api.example.test`), with the e2e cookie Domain set. Bigger change, keeps every e2e line.
  3. A test-only switch in `csp.ts` that drops `upgrade-insecure-requests` when an e2e env var is set. Smallest code change, but it weakens a production header path, so it needs the owner's approval.
- Before Phase 23: leftover.md L1 (Stripe test keys) and L2 (admin screenshots, now needs C3.1.10).
- Manual check (not blocking): sign in to the admin host as an MFA-enabled platform admin and confirm the session start and the refusal page.
