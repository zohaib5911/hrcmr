# STATUS
Updated: 2026-11-09 01:14 (Europe/London)    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: f986a6c
State: IN PROGRESS — AUDIT-3 fixes (changesneeded.md C3.1.1 to C3.1.16), small model

## Last completed
- AUDIT-3 round 1 (Opus) — 0 P0 / 10 P1 / 6 P2, written to changesneeded.md. api 1319, web unit 802, e2e 437 (200 skipped) at audit.

## Current task
- AUDIT-3 fixes — changesneeded.md, top to bottom, one item per commit, ticked with its fix commit.
  - [ ] C3.1.1 refund of a 10-year plan ends the plan (fix in progress)
  - [ ] C3.1.2 platform session started from the browser
  - [ ] C3.1.3 e2e platform-admin seed
  - [ ] C3.1.4 to C3.1.10 admin screens (overview, companies, users, subscriptions, queues, settings, jobs and audit)
  - [ ] C3.1.11 to C3.1.16 (P2)
- Resume note: run `bash .agent/next.sh`; it prints the first unticked C3.1.x item.

## Next tasks
- Finish changesneeded.md, then BLOCKED — re-audit requested (AUDIT-4) per the loop in AGENTS.md §6.
- T19.16, T19.17, T20.5, leftover.md L1 (Stripe keys), before Phase 23.

## Health
- CI on dev: green at PR #26 (12/12). Not re-run for the audit fixes yet.
- Local checks: C3.1.1 — tests/db/test_platform_billing.py + tests/db/test_billing.py 29 pass; ruff, ruff format, mypy clean on touched files.

## Issues / suggestions
- **E2E admin host has no client JavaScript (found in C3.1.3).** The admin host is plain http in the tests, and the production CSP adds `upgrade-insecure-requests` (lib/security/csp.ts), so the browser upgrades the admin page's `_next` script and CSS requests to https, and they fail (ERR_SSL_PROTOCOL_ERROR). Server-rendered admin pages still work. Any C3.1.4 to C3.1.10 screen with a client component cannot be exercised in e2e until this is solved. Options for the owner or a big model: serve the e2e admin host over https, or a test-only CSP switch. Do not just drop the CSP directive.
- **E2E admin host cannot call the API from the browser (found in C3.1.3).** The API is on 127.0.0.1:8100 and the admin host is a different site, so the SameSite=Lax session cookies are not sent. In production both are one site. The admin screens' API calls will fail in e2e for the same reason. tests/support/platform.ts copies the platform cookie to the admin host.
- Run tests/test_architecture.py and tests/test_openapi.py as separate commands from tests/db (known fixture order issue).

## Strategy / decisions taken
- Fix one changesneeded item per commit, then one `chore(audit)` commit that ticks it with the fix commit's sha.
- C3.1.1: a 10-year refund ends the plan in the same step as `_refunded()` (plan free, status refunded, ends now); annual refunds stay as they are.
- C3.1.2 (replaces owner answer 7's "forwards Set-Cookie"): the session start is made by the browser. `/session` is a server page rendering `components/platform/session-start.tsx`, which calls the API with `createApiClient` (no enrolment redirect, so a refusal reaches `/session-required`). The layout lets `/session` through. The cookie is set on the shared `.<domain>`, so the admin host sees it.

## Owner actions needed
- None for the audit fixes. Before Phase 23: leftover.md L1 (Stripe test keys).
