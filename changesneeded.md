# changesneeded.md — audit AUDIT-3 round 2 (2026-11-12, gpt-6.1-sol)
Scope: f986a6c..0d1addd (C3.1.1–C3.1.16 fixes and regressions; Phase 18–20 additions excluded). Tests at audit: api incomplete (stalled at 42%, interrupted; no final p/f/s summary), RLS CLI passed; web unit 1255/0, e2e 473/0/220 skipped; CI latest dev run green.
Counts: 1 P0 / 4 P1 / 1 P2. FIX NEEDED.

### [ ] C3.2.1 · P0 · Make the required full API suite finish (from AUDIT-3) · B
- **Problem:** `cd api && uv run pytest -q` stopped advancing after 584 progress dots (42%, around the transition into `tests/db/test_soc_public.py`) for several minutes. Interrupt also stalled during pytest-asyncio runner teardown; process required SIGTERM. No final counts were produced. STATUS already notes a test-order problem involving architecture/OpenAPI collection, but the cause of this hang is unconfirmed.
- **Fix:** reproduce with verbose test names and a bounded traceback timer (`pytest -vv -o faulthandler_timeout=120`); inspect fixture/background-task teardown around the stalled test and collection side effects in `tests/test_architecture.py` / `tests/test_openapi.py`. Correct the resource/task lifecycle or collection pollution found; do not skip tests, weaken assertions or split away tests merely to hide the required command's failure. Capture exact stalled test and cause in the PR.
- **Done when:** `bash /home/zohaib/cmr_hr/.agent/bus.sh serial -- bash -c 'cd api && uv run pytest -q'` exits 0 with real counts and no hung teardown.

### [x] C3.2.2 · P1 · Use the configured browser API URL for platform session start and CSV export (from C3.1.2, C3.1.10) — fixed in PR #64
- **Problem:** `web/components/platform/session-start.tsx:20` and `audit-admin.tsx:61` call `browserApiBaseUrl()` with default `process.env`. Next.js does not inline dynamic property access through an env object. The built session chunk still calls the helper without arguments; the helper reads `env.NEXT_PUBLIC_API_URL`, falling back to `http://localhost:8000/api/v1` (or throwing). Session tests inject `run` and never exercise `startFromBrowser`; e2e seeds the cookie directly. CSV href is also wrong after client hydration.
- **Fix:** supply explicit `process.env.NEXT_PUBLIC_API_URL` and `process.env.NODE_ENV`, copying `baseUrl()` in `web/lib/auth/request.ts`; share an appropriate browser-safe helper if useful. Cover the real `startFromBrowser` request path with fetch mocked, including success and refusal. Cover the export link's configured origin and filters.
- **Done when:** platform unit tests assert POST goes to the configured API origin with CSRF and credentials; production build's browser session flow and hydrated CSV URL use the configured origin. Lint/typecheck and targeted unit tests pass.

### [ ] C3.2.3 · P1 · Preserve the admin allowlist for server-rendered platform pages (from C3.1.2, C3.1.4–C3.1.10) · B
- **Problem:** `web/lib/platform/guard.ts:8-15` forwards only cookies. All new SSR data calls reach `api/app/modules/rbac/platform.py:require_platform`, which always calls `require_allowed_network`. The checked IP and audited user agent are therefore the web server's, even though session start was moved into the browser. With an allowlist containing the real admin's IP, browser session start succeeds but overview/companies/settings/jobs/audit requests are refused and redirect back to start. Adding the server IP would defeat visitor network checks on this path.
- **Fix:** implement a trustworthy visitor identity strategy for SSR (authenticate the internal hop and derive visitor identity only from verified ingress, or move restricted requests into the browser). Decide and record the approach on the bus. Never trust arbitrary forwarded headers or exempt the platform guard from allowlisting. Preserve page/action auditing and production CSP.
- **Done when:** integration coverage exercises an allowed visitor and denied visitor through the SSR path, refuses forged forwarding headers from untrusted callers, and asserts the recorded visitor identity; allowed admins can render data with ADMIN_IP_ALLOWLIST configured.

### [ ] C3.2.4 · P1 · Validate platform sessions on queues, contact, users and subscriptions pages (from C3.1.4, C3.1.6–C3.1.8)
- **Problem:** queues/contact/users server pages accept any present platform cookie without an API validation call. They do not audit those page views or redirect expired sessions before rendering. Subscriptions uses `isPlatformOwner()`, which silently turns context 401/403 into owner=false. Browser `fail()` handlers in these components redirect only UNAUTHENTICATED, missing the shared 403 rule. This fails the previous requirement that every screen use the shared expired-session guard.
- **Fix:** use an authenticated platform read and `dataOrSessionRedirect` on each page (coordinate with C3.2.3's trusted SSR strategy); do not swallow authentication refusal in owner lookup. Cover 401 and 403 on page entry and browser expiry while retaining normal action errors. Keep sensitive data protected by the API.
- **Done when:** tests for each page cover absent, invalid/expired and valid platform sessions; refusals return to `/session?next=<public path>`, successful page views are audited, and component tests cover expired-session outcomes.

### [ ] C3.2.5 · P1 · Expose subsequent contact and queue records (from C3.1.8)
- **Problem:** `web/components/platform/contact-admin.tsx` and `queues-admin.tsx` request no offset/limit, discard response totals, and expose no paging. Their APIs default to 50 rows; the 51st outstanding contact message or deletion/export request is unreachable.
- **Fix:** add independent offset/total state and accessible Previous/Next controls for the contact list and both queue lists; preserve status filters and reset each affected offset on filter changes. Copy subscriptions paging. Avoid stale-filter response races.
- **Done when:** unit tests cover more than 50 results, second-page requests and filter resets for all three lists, including empty/error states.

### [x] C3.2.6 · P2 · Link Settings from the admin overview (from C3.1.4, C3.1.9) — fixed in PR #67
- **Problem:** `web/components/platform/overview.tsx:ADMIN_LINKS` omits `/settings`; the overview is the admin navigation hub and was required to link every added screen.
- **Fix:** add a Settings link alongside the existing admin screens and assert its public href in `overview.test.tsx`.
- **Done when:** overview unit tests pass and the Settings link opens `/settings`.

## Notes (no action needed)
- Reviewed all sixteen prior fix areas. Refund entitlement/webhook handling, owner lock protection, caller-scoped support context, watcher URL allowlist, comp banner, independent export, token colour and code-hash exclusion match the requested fixes.
- Added screenshot skips follow phase-gate policy; the admin SSR-only browser coverage follows the recorded decision. That decision does not prove the real session-start browser request works; C3.2.2 addresses the gap.
- Register status/rerun remains explicitly moved to T20.5. Phase 18–20 calculators and register work are outside this re-audit scope.
