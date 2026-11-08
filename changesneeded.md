# changesneeded.md — audit AUDIT-3 round 1 (2026-11-09, Claude Opus 5.5)
Scope: audit-pass-2..55153b7 (128 commits, T15.1 → P17)   Tests at audit: api 1319/0/0 (ruff, format, mypy clean; check-rls via tests/db/test_cli.py 4/0, the bare CLI needs deploy env vars), web unit 802/0, lint/types/gen:api/build clean, e2e 437/0 (200 screenshot-only skipped), CI green (PR #26)
Counts: 0 P0 / 10 P1 / 6 P2. FIX NEEDED.

Order: do the items top to bottom. C3.1.3 (the e2e seed) comes before the admin screens, because their e2e tests need it.
Admin screens (C3.1.4 to C3.1.10): copy `web/components/platform/rules-editor.tsx` (components/ui only, `attempt()` from
`lib/auth/request`, `PageHeader`, `ConfirmDialog`, `formatUk`) and its page `web/app/(admin)/platform/rules/page.tsx`.
Pages live under `web/app/(admin)/platform/<name>/page.tsx`; the browser sees them at `/<name>` on the admin host.
Each screen needs loading, empty and error states, works at 360 px and in dark mode, and has one unit test file
(copy `web/components/platform/platform-bar.test.tsx` style) plus one e2e spec using the C3.1.3 seed.

### [x] C3.1.1 · P1 · A platform refund of a 10-year plan leaves the company on its paid plan (from T17.4) — fixed in e4f21f8
- **Problem:** `api/app/modules/platform_admin/billing.py` `refund()` sets `subscription.refunded_at` (and `status = "refunded"` for ten_year) but never changes the company. The plan was meant to change on Stripe's `charge.refunded` webhook, but `api/app/modules/billing/service.py` `_refunded()` returns early when `row.refunded_at is not None` (line ~318), so it never ends the plan. Result: the company keeps `plan = "ten_year"`, `subscription_status = "active"`, and `is_entitled()` stays True after a full refund.
- **Fix:** in `refund()`, after a successful Stripe call, for `subscription.plan == "ten_year"`: load the company (`await db.get(Company, subscription.company_id)`) and, if `company.plan == "ten_year"`, set `company.plan = "free"`, `company.subscription_status = "refunded"`, `company.subscription_ends_at = now` (the same three lines as `_refunded()` in billing/service.py). Leave annual as it is (an annual refund does not cancel; say so in the docstring). Fix the module docstring, which says the plan changes on the webhook.
- **Done when:** a new test in `api/tests/db/test_platform_billing.py`, next to `test_an_owner_refunds_a_ten_year_payment_once_and_it_is_audited`: after the refund the company row has `plan == "free"` and `subscription_status == "refunded"`; then a `charge.refunded` webhook for the same payment changes nothing and does not fail. `uv run pytest tests/db/test_platform_billing.py tests/db/test_billing.py -q` pass.

### [x] C3.1.2 · P1 · Platform session start is sent from the web server, so the API sees the server's address (from T17.1) — fixed in 8f4ca0e
- **Problem:** `web/app/(admin)/platform/session/route.ts` calls `POST /auth/platform-session` from the Next.js server (`lib/platform/session.ts` `startPlatformSession`). The API's `require_allowed_network` (`api/app/modules/rbac/platform_session.py`) and the `platform.session.started` audit row then use the web server's IP and user agent, not the admin's. With `ADMIN_IP_ALLOWLIST` set, either every admin is refused, or the allowlist must include the web server's address, which lets everyone through. Every later platform request comes from the browser, so only the start is wrong.
- **Fix:** start the session from the browser. Replace `route.ts` with a client page `web/app/(admin)/platform/session/page.tsx` (+ a small client component in `web/components/platform/session-start.tsx`) that, on mount, calls `attempt((api) => api.POST("/auth/platform-session"))` (the same client the rules editor uses, which sends the CSRF header and the cookies), then `window.location.replace(safeNextPath(next))` on success, or `window.location.replace("/session-required?code=" + code)` on refusal. Keep `safeNextPath`, `refusalMessage` and `hasPlatformCookie` in `lib/platform/session.ts`; delete `startPlatformSession` and its tests once unused. Show "Starting a platform session…" while it runs. Record the change under "Strategy / decisions" in STATUS (it replaces owner answer 7's "forwards Set-Cookie").
- **Done when:** unit test for the new component (success → replace to next; refusal → session-required with the code; unsafe next → `/`); `web/tests/e2e/host-routing.spec.ts` still passes (the `/` → `/session?next=%2F` redirect is unchanged); `pnpm lint && pnpm typecheck && pnpm test` pass.

### [x] C3.1.3 · P1 · e2e seed for a platform admin (prerequisite for the admin screens; closes leftover.md L2's blocker) — fixed in e2b9e7b (see STATUS Issues: the admin host runs no client JavaScript in e2e)
- **Problem:** no browser test can reach the admin screens: `api/tests/e2e_server.py` has no platform admin, and the admin host is not mapped in the browser (leftover.md L2).
- **Fix:** in `api/tests/e2e_server.py` add a test-only route `POST /api/v1/e2e/platform-admin` (copy `paid_plan`, `include_in_schema=False`) that makes a given signed-up user a platform admin (`platform_admins` row, level from the body: `owner` or `support`), marks the email verified and turns on MFA with a known TOTP secret (copy how `web/tests/support/accounts.ts` already signs in an MFA user, if it does; otherwise set `mfa_enabled` and a secret and add a TOTP helper in `web/tests/support/`). Map the admin host in Playwright: in `web/playwright.config.ts` add a project or `launchOptions.args: ["--host-resolver-rules=MAP admin.example.test 127.0.0.1"]` so a page can open `http://admin.example.test:<port>/`. Add `web/tests/support/platform.ts` with `signInPlatformAdmin(page, level)`.
- **Done when:** a new `web/tests/e2e/platform-admin.spec.ts` signs in a platform owner, opens the admin host `/`, is sent through `/session` and lands on the admin landing page with the red bar; and a support-level admin does the same. `pnpm test:e2e tests/e2e/platform-admin.spec.ts` passes. Update leftover.md L2 (seed done; screenshots go with C3.1.10).

### [ ] C3.1.4 · P1 · Admin screen: overview metrics on the admin landing page (from T17.2)
- **Pattern:** read the "Admin screens" paragraph at the top of changesneeded.md first (files to copy, states, tests).
- **Problem:** `web/app/(admin)/platform/page.tsx` is two links. Plan L1160 (overview) has no screen; `GET /platform/metrics` is unused.
- **Fix:** landing page shows the `GET /platform/metrics` figures as stat cards (signups 24 h / 7 days, active companies, plans, paid entitled, MRR/ARR estimate in £, churn and refunds over 30 days, job queue depth from `GET /platform/jobs/queue`), and a nav list linking every admin screen built in C3.1.5–C3.1.10 plus the existing rules, courses and dossier links. When an API call answers 401/403, send the browser to `/session?next=<this path>` instead of `notFound()` (fixes the STATUS issue "cookie expired → 404"); put that in one helper in `lib/platform/` and use it on every admin screen.
- **Done when:** unit test renders the cards from a fixture; e2e (C3.1.3 seed) sees the "Active companies" card.

### [ ] C3.1.5 · P1 · Admin screen: companies list, detail and actions, start support mode (from T17.2, T17.3) · S!
- **Pattern:** read the "Admin screens" paragraph at the top of changesneeded.md first (files to copy, states, tests).
- **Problem:** no screen for `GET /platform/companies`, `GET /platform/companies/{id}`, suspend / reactivate / extend-plan / mark-for-deletion, or `POST /platform/companies/{id}/impersonate`. Support mode can only be started with curl.
- **Fix:** `/companies` list (search box, plan and status filters, paging) and `/companies/[id]` detail (profile, plan and Stripe ids, people, recent platform actions). Actions each in a `ConfirmDialog` with a required reason: Suspend or Reactivate (by status), Extend plan (days), Mark for deletion (only shown to an owner; the API still checks). "Start support mode" asks for reason and ticket ref, calls impersonate, then opens the tenant app (`web_origin`) in the same tab. Owner only: "Turn on writes" for a live support session (`POST /platform/impersonation/{id}/writes` with `confirm: true`, second confirmation in the dialog) and "End" (`.../end`).
- **Watch:** never show the support cookie or token; the reason is required in the UI and the API; a support-level admin must not see the owner-only buttons.
- **Done when:** unit tests for the dialogs (reason required); e2e: an owner suspends then reactivates a seeded company and the status chip changes; a support admin does not see "Mark for deletion".

### [ ] C3.1.6 · P1 · Admin screen: users search, lock and unlock (from T17.2)
- **Pattern:** read the "Admin screens" paragraph at the top of changesneeded.md first (files to copy, states, tests).
- **Problem:** no screen for `GET /platform/users` and lock/unlock.
- **Fix:** `/users` with an e-mail search (3 characters or more), result rows with status, and Lock / Unlock in a `ConfirmDialog` with an optional reason.
- **Done when:** unit test; e2e: an owner locks then unlocks a seeded user.

### [ ] C3.1.7 · P1 · Admin screen: subscriptions and refunds (from T17.4) · S!
- **Pattern:** read the "Admin screens" paragraph at the top of changesneeded.md first (files to copy, states, tests).
- **Problem:** no screen for `GET /platform/subscriptions` or `POST /platform/refunds`.
- **Fix:** `/subscriptions` list (plan and refunded filters, paging, Stripe ids shown as text). "Refund" only for an owner and only on rows with no `refunded_at`: dialog with required reason and a second confirmation that sends `confirm: true`. Show the API's error message on refusal (`ALREADY_REFUNDED`, `NOTHING_TO_REFUND`, `PAYMENTS_NOT_SET_UP`).
- **Watch:** do the refund request once per click (disable the button while busy); never type an amount.
- **Done when:** unit test (button hidden for support level; confirm sends `confirm: true`); e2e shows the list (the e2e server has no Stripe, so the refund itself is a unit test only).

### [ ] C3.1.8 · P1 · Admin screens: deletion and export queues, contact inbox (from T17.4)
- **Pattern:** read the "Admin screens" paragraph at the top of changesneeded.md first (files to copy, states, tests).
- **Problem:** no screens for `GET /platform/deletion-requests`, `GET /platform/data-exports`, `GET/PATCH /platform/contact-messages`.
- **Fix:** `/queues` with two tables (deletion requests by status; data exports by status) and `/contact` (handled / not handled filter, open a message, "Mark handled" / "Mark not handled").
- **Done when:** unit tests; e2e opens both pages and sees the empty states.

### [ ] C3.1.9 · P1 · Admin screens: settings (terms publish, feature flags, announcements) (from T17.5)
- **Pattern:** read the "Admin screens" paragraph at the top of changesneeded.md first (files to copy, states, tests).
- **Problem:** no screens for `/platform/terms-versions`, `/platform/feature-flags`, `/platform/announcements`.
- **Fix:** `/settings` page with three cards: terms versions list + "Publish new version" (owner only; second confirmation that says every user must accept again); feature flags list with a switch per flag (`PUT /platform/feature-flags/{key}`); announcements list + create (message, region, start, end) + "End now".
- **Done when:** unit tests; e2e: an owner creates an announcement and the tenant app shows the `AnnouncementBanner`, then ends it.

### [ ] C3.1.10 · P1 · Admin screens: jobs and platform audit log, then phase screenshots (from T17.6, P17)
- **Pattern:** read the "Admin screens" paragraph at the top of changesneeded.md first (files to copy, states, tests).
- **Problem:** no screens for `/platform/jobs/*` and `/platform/audit*`. P17's screenshots were never taken (leftover.md L2).
- **Fix:** `/jobs` (queue depth, failures table, "Run again" for allow-listed jobs with a required reason) and `/audit` (filters: action family, actor, date range; paged table; "Export CSV" link to `/platform/audit/export` with the same filters). Then add the admin pages to a `web/tests/e2e/phase17-screenshots.spec.ts` (copy `phase16-screenshots.spec.ts`; 390 and 1280 px, both themes) and run it once. Tick leftover.md L2.
- **Done when:** unit tests; e2e opens both pages; the screenshots exist under the same folder as phase 16's.

### [ ] C3.1.11 · P2 · A data export can only be asked for inside the delete-account flow (from T16.4)
- **Problem:** nothing in `web/` calls `POST /companies/me/export`; the only way to get an export is to start deleting the company (`delete-account-page.tsx`). Plan 8.16 lists the export as its own feature.
- **Fix:** add an "Export all your data" card to `web/components/company/billing-page.tsx` (Company Admins only, as the rest of the page): button → the same password step-up dialog `delete-account-page.tsx` uses → `POST /companies/me/export`; show "We are preparing your export. We will e-mail you a link." and the `EXPORT_IN_PROGRESS` message on 409.
- **Done when:** unit test for the card (step-up asked, success and 409 messages); `pnpm test` pass.

### [ ] C3.1.12 · P2 · A support-level platform admin can lock an owner (from T17.2)
- **Problem:** `api/app/modules/platform_admin/users.py` `lock()` only refuses your own account. Any platform admin can lock another platform admin, including an owner.
- **Fix:** in `router.py` `lock_user`, if the target user has a `platform_admins` row and the caller is not an owner (`_is_owner(access)`), raise `ForbiddenError("Only an owner can lock a platform admin.")`.
- **Done when:** test in `api/tests/db/test_platform_admin.py`: support admin locking an owner → 403 and the owner stays active; owner locking a support admin → 200.

### [ ] C3.1.13 · P2 · The rules watcher fetches whatever URLs the live version stored (from T15.7)
- **Problem:** `api/app/modules/soc_rules/watch.py` line ~53 takes the URLs from `live.source_urls` in the database. Only `PAGE_URLS` (www.gov.uk) should ever be fetched (SSRF rule).
- **Fix:** fetch `PAGE_URLS[kind]` from `soc_rules/source.py` instead; still compare against the stored list and return `fetch_failed` if a stored URL differs.
- **Done when:** a test in the watcher's test file: a live version whose `source_urls` names another host → `fetch_failed` and no request is sent (use the existing fake client).

### [ ] C3.1.14 · P2 · Comp access is not shown on the billing page (from T17.6 comp)
- **Problem:** `GET /billing/subscription` returns `comp_until`; `web/components/company/billing-page.tsx` ignores it, so a company with comp access looks like a free plan and is offered Checkout.
- **Fix:** when `comp_until` is in the future, show an info `Alert` "Complimentary access until <date>" above the plan card.
- **Done when:** unit test with a fixture that has `comp_until` set.

### [ ] C3.1.15 · P2 · Admin red is a raw hex colour (from T17.1, T17.3)
- **Problem:** `web/components/platform/platform-bar.tsx:12` and `web/components/app/support-banner.tsx:40` use `bg-[#b00010]`; every other colour is a token in `web/app/globals.css`.
- **Fix:** add `--fixed-admin: #b00010` next to `--on-fixed` in each theme block of `globals.css` and `--color-fixed-admin: var(--fixed-admin)` in the `@theme` block; use `bg-fixed-admin` in both files. Add the token to `web/tests/support/expected-tokens.ts` if that file lists them.
- **Done when:** `pnpm lint && pnpm typecheck && pnpm test` pass; no `#b00010` left outside `globals.css`.

### [ ] C3.1.16 · P2 · The deletion code hash is in the data export (from T16.4)
- **Problem:** `api/app/modules/exports/archive.py` `NEVER_EXPORTED` does not list `code_hash`, so `tables/deletion_requests.csv` carries it while a request is waiting for its code.
- **Fix:** add `"code_hash"` to `NEVER_EXPORTED`.
- **Done when:** a check in `api/tests/db/test_exports.py` that no exported header is `code_hash`; that file passes.

## Notes (no action needed)
- Three going rates checked against the live GOV.UK Appendix Skilled Occupations page on 2026-11-09: 1111 £88,100 (£45.18/h), 2136 £41,200 (£21.13/h), 3544 £34,900 (£17.90/h); all match the stored data. The £41,700 general threshold matches Appendix Skilled Worker option A. Every figure is parsed from the saved pages with their SHA-256 sidecars.
- Support mode (T17.3), the platform guard, the purge executor (T16.5) and the Stripe webhook (T16.1) were read in full: grants are re-checked every request, writes need the owner switch, audit rows carry the support session, purge runs in one transaction with the history-delete guard.
- CV match (T15.5) strips links, e-mails, phones, postcodes and street addresses as the plan says; the candidate's name (usually the CV's first line) still goes to the AI. Owner decision if names should be removed too.
- Route prefixes are mixed: `/platform/*` and the older `/admin/*` (courses, dossier links). Not worth moving now.
- MRR/ARR estimate uses a £50 constant in `platform_admin/metrics.py` (documented, display only).
- An annual refund from the platform screen does not cancel the subscription (it is a refund of one payment, e.g. a duplicate charge). Intended.
