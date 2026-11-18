# changesneeded.md — audit AUDIT-6 round 1 (2026-11-16, claude-fable-5-2)
Scope: whole project at 91387bc (owner-requested full audit: bugs, vulnerabilities, speed, UI).   Tests at audit: api 1437/0/0 (ruff and mypy clean), web unit 1485/0 in 120 files (2 files and the type-check could not load in the main checkout: stale node_modules, see Notes), e2e not run, CI green on the last dev run (2026-11-13)

Counts: 1 P0 (fixed in this PR) / 3 P1 / 8 P2 bugs and vulnerabilities, then 7 speed items (`O`) and 9 UI items (`U`).
How each finding was checked is written in its **Evidence** line (code read, command run, or advisory looked up). Nothing here is a guess; anything I could not prove is in "Notes", not in an item.
Part 1 items are for any agent. Part 2 and Part 3 items are tagged `· B` where they need design judgement; **the owner should read Part 3 before the runners start**, because it changes how the product looks.

What was scanned: all 436 API routes mapped to their permission guard (the only unguarded ones are the intended public, auth and webhook routes), sessions, CSRF, rate limits, tenant isolation (RLS + query scoping), RBAC matrix, uploads and virus scan, Stripe webhook and billing, support mode, platform admin, AI redaction, document parsers, PDF rendering, the Next.js proxy, CSP and host routing, Dockerfiles, CI workflows, both dependency lockfiles, the design tokens and the Phase 25 screenshots.

---

# Part 1 — Bugs and vulnerabilities

### [x] C6.1.1 · P0 · Two locked Python packages have published vulnerabilities; the CI audit job will fail — fixed in this audit's PR
- **Problem:** `api/uv.lock` pins `dnspython 2.9.0` (pulled in by `email-validator`) and `opentelemetry-api 1.45.1` (pulled in by `fastapi`). Both now have advisories, so the `audit` job in `.github/workflows/ci.yml:250` fails on the next PR and blocks every merge.
- **Evidence:** `uvx pip-audit` on the exported lock, run 2026-11-16, reports both. Looked up on OSV: GHSA-vvf4-9x63-8xvv / CVE-2026-128089 (dnspython, HIGH: a WKS record makes the zone-file parser allocate huge memory; fixed in 2.9.2) and GHSA-mf5v-w3w3-f6cg / CVE-2026-126360 (opentelemetry-api, MODERATE: quadratic-time `traceparent` parsing blocks the event loop; fixed in 1.45.2). The app parses no zone files, so the first is not reachable; the second is reachable if FastAPI extracts trace context from request headers, so treat it as real.
- **Fix (done by the auditor, the CI-green exception in audit.md):** `uv lock --upgrade-package dnspython --upgrade-package opentelemetry-api`; the lock now has `dnspython 2.9.2` and `opentelemetry-api 1.45.2`. dnspython 2.9.2 is younger than the 14-day cooldown, so `api/pyproject.toml` has a dated `exclude-newer-package` entry for it, like certifi and pypdf before; remove it after 2026-11-18.
- **Done when:** `uv export --no-hashes --no-dev | uvx pip-audit -r /dev/stdin` reports no vulnerabilities, and `uv run pytest -q` still passes.

### [x] C6.1.2 · P1 · A company admin can switch off two-step verification for a person's whole account, in every company — fixed in PR #147
- **Problem:** `POST /users/{membership_id}/reset-two-step` (`api/app/modules/access/router.py:341`, line 355 `auth.auth.disable_mfa(user)`) clears `mfa_secret`, `mfa_enabled` and the recovery codes on the **global** `users` row and signs the person out everywhere. The only checks are the caller's own step-up and the target's role in the caller's company. A person who belongs to company A and company B (an accountant, an adviser), or who is also a **platform admin**, loses their second factor for B and for the admin site because an admin of A asked. Anyone can create company A for free. Self-service `POST /auth/mfa/disable` refuses in exactly these cases (`_policy_requires_mfa`, `auth/router.py:341`), and the deletion job protects multi-company users and staff (`jobs/deletion.py:_people`), so this route is the odd one out.
- **Evidence:** code read end to end; `User` has no `company_id` (`identity/models.py`), and there is no test for a target with a second membership (`tests/db/test_user_access.py`).
- **Fix:** in `reset_two_step`, before `disable_mfa`: refuse with `ForbiddenError("This person also has access elsewhere, so only they or support can reset their two-step verification.")` when the target user (a) has a `PlatformAdmin` row, or (b) has a membership in any other company. Check (b) on the `GlobalDb` session with `db.act_as(user.id)` the way `_policy_requires_mfa` reads memberships. On success, send the target a security e-mail (add a `two_step_reset` template next to `password_changed`) so a reset is never silent.
- **Done when:** new tests in `tests/db/test_user_access.py`: reset is 403 for a target who is a platform admin; 403 for a target with a membership in a second company (their `mfa_enabled` stays true and their sessions stay live); still 200 for a single-company target, who receives the e-mail.

### [x] C6.1.3 · P1 · Changing a password has no attempt limit, so a stolen session can guess the current password — fixed in PR #148
- **Problem:** `POST /auth/change-password` (`api/app/modules/auth/router.py:229`, check at line 240) verifies `current_password` with no rate limit and no lockout. Step-up exists to stop a hijacked session from doing sensitive things, and `step_up` is limited to 5 tries per 5 minutes (`auth/service.py:343`), but this endpoint answers the same question ("is this the password?") without any limit, so it is a way round it. A correct guess also changes the password and ends every other session.
- **Evidence:** code read; no `RateLimiter` call on this path. OWASP ASVS 2.2.1 and the OWASP Authentication Cheat Sheet require throttling on every credential check, not only on sign-in.
- **Fix:** at the top of `change_password`, call the same limiter `step_up` uses: `RateLimiter(auth.redis).hit("stepup-user", str(caller.user_id), limit=5, window_seconds=300)` and raise `RateLimitedError(result.retry_after)` when refused (sharing the bucket means the two routes cannot be combined for 10 tries). Write an `auth.password.change_failed` security event on a wrong password and commit it before raising, as `step_up` does.
- **Done when:** a test makes 5 wrong attempts then gets 429 on the 6th, with the right password also refused until the window ends; existing change-password tests pass.

### [x] C6.1.4 · P1 · A rate-limit counter can be left without an expiry and then blocks that person or address for ever — fixed in PR #149
- **Problem:** `RateLimiter.hit` (`api/app/core/rate_limit.py:41-42`) runs `SET key 0 EX window NX` and then `INCR key` as two commands. If the old window ends between them, `INCR` creates a new key with **no expiry**. The counter then only grows; once past the limit that e-mail, user or IP is refused for ever (`ttl` is -1, so `retry_after` just reports the window length each time). It hits the busiest keys first: `login-account` (10 per hour per e-mail), `public-ip`, the AI limit.
- **Evidence:** reproduced against the local Redis: with the key set to expire in 40 ms, the limiter's two calls 80 ms apart return `count 1 ttl -1`. Redis documents this hazard in the INCR "rate limiter" pattern and gives the atomic fixes.
- **Fix:** make it one atomic step: a small Lua script registered once with `self._redis.register_script` (`INCR`; if the result is 1 or `TTL` is -1 then `EXPIRE key window`; return count and ttl). Keep the method's signature and return value.
- **Done when:** a new test in the limiter's test file creates the key with no expiry, calls `hit`, and shows the key now has a positive TTL; all current rate-limit tests pass.

### [x] C6.1.5 · P2 · A non-ASCII character in the CSRF header or Stripe signature gives a 500 instead of a refusal — fixed in PR #150
- **Problem:** `hmac.compare_digest` raises `TypeError` for `str` values that are not ASCII. `api/app/core/csrf.py:66` compares the cookie with the header as strings, and `api/app/integrations/stripe.py:119` compares signature strings. Header bytes above 0x7F reach both (Starlette decodes headers as latin-1), so anyone can make these two paths return 500 and fill the error log and Sentry.
- **Evidence:** `python3 -c "import hmac; hmac.compare_digest('abc','ab\xe9')"` raises `TypeError: comparing strings with non-ASCII characters is not supported` (Python docs, `hmac.compare_digest`).
- **Fix:** compare bytes in both places: `hmac.compare_digest(cookie.encode("utf-8"), supplied.encode("utf-8"))`; same for `expected`/`given` in `verify_signature`.
- **Done when:** tests send `X-CSRF-Token: é` (expect 403 `CSRF_INVALID`) and a `Stripe-Signature` with `v1=é` (expect 400 `WEBHOOK_SIGNATURE_INVALID`).

### [x] C6.1.6 · P2 · The CSRF token is a bare double-submit cookie shared with every subdomain — fixed in PR #171
- **Problem:** `CsrfMiddleware` (`api/app/core/csrf.py`) accepts any request whose header equals the `csrf` cookie, and the cookie is set with `Domain=.DOMAIN`. The token is not tied to the session and is never changed at sign-in. Anything that can set a cookie for the parent domain (a future subdomain with user content, a subdomain takeover) can plant its own token and pass the check. OWASP's CSRF Prevention Cheat Sheet calls this the "naive double-submit" weakness and recommends the signed variant bound to the session.
- **Evidence:** code read. Not exploitable today (no such subdomain exists, SameSite=Lax is the first lock), which is why this is P2 hardening.
- **Fix:** issue the token as `<random>.<HMAC-SHA256(session_secret, random + "|" + session cookie value or "anon")>` and verify the HMAC in the middleware as well as the equality; issue a fresh token when the session cookie changes (sign-in, MFA, company switch). The web client needs no change (it copies the cookie into the header).
- **Done when:** tests show a token minted for one session cookie is refused with another, a hand-made `csrf=x` + `X-CSRF-Token: x` pair is refused, and the existing CSRF tests pass.

### [x] C6.1.7 · P2 · An invitation added to an account nobody has verified leaves the original password working — fixed in PR #155
- **Problem:** `sign_up` lets anyone create an account for an address they do not own (it stays unverified). If that address is later invited, `accept_invite` (`api/app/modules/auth/accounts.py`, the `existing` branch) attaches the new company to that account and keeps the password the stranger chose. Access is still blocked until the address is verified, so the risk needs the real owner to click a verification link they did not ask for, but after that the stranger's password opens the invited company. This is the "pre-hijacked account" pattern (Sudhodanan and Paverd, USENIX Security 2022).
- **Evidence:** code read: no check of `existing.email_verified_at` in `accept_invite`.
- **Fix:** in `accept_invite`, when `existing.email_verified_at is None`, treat the invitee as new: require `password` and `accept_terms`, replace `password_hash`, set `email_verified_at`, clear the `mfa_*` fields, `revoke_all` sessions, and return the user so they are signed in. Make `invitation_details` report `has_account=False` for that case so the web form asks for a password.
- **Done when:** a test signs up an address (unverified), invites it from another company, accepts with a new password, and shows the old password no longer signs in while the new one does.

### [x] C6.1.8 · P2 · The CV match reads a 10 MB PDF before it checks the AI rate limit — fixed in PR #151
- **Problem:** `POST /soc/resume-match` (`api/app/modules/soc/cv_router.py:90`) virus-scans and runs `pypdf` text extraction in a worker thread (which cannot be cancelled) before `generate()` applies `AI_PER_USER`. A signed-in user can loop crafted PDFs and keep the thread pool busy without ever being limited.
- **Evidence:** code read; the limiter is only inside `app/ai/service.py:generate`.
- **Fix:** move the limit to the start of the route: add `async def check_ai_limit(request, access)` in `app/ai/service.py` (the existing block from `generate`), call it right after `ai_ready`, and let `generate` take `limit_checked=True` to skip the second count.
- **Done when:** a test sends 31 requests with an unreadable PDF and gets 429 on the 31st; existing AI tests pass.

### [x] C6.1.9 · P2 · The careers apply form adds a stranger's CV and application to an existing candidate with the same e-mail — fixed in PR #157
- **Problem:** `apply` (`api/app/modules/recruitment/public.py`) looks the candidate up by e-mail only and attaches the new application and uploaded file to that record. A visitor who knows an applicant's address can put files and applications on their record, and can make the platform send an `application_received` e-mail to any address.
- **Evidence:** code read; Turnstile and 20 per hour per address limit the volume, so P2.
- **Fix:** keep matching by e-mail (recruiters want one record), but mark what came in unconfirmed: add a `needs_review` flag on applications that arrive from the public form for a candidate who already existed, shown in the application list ("Sent from the public form; details not confirmed"). Never overwrite the stored name or phone from the form (already true; add the test).
- **Done when:** a test applies twice with the same e-mail and different names: one candidate, original name kept, second application flagged.

### [x] C6.1.10 · P2 · No error pages: an unexpected rendering error shows the framework's bare screen — fixed in PR #152
- **Problem:** there is no `error.tsx` or `global-error.tsx` anywhere under `web/app` (only `not-found.tsx` and six `loading.tsx`). A thrown error in any page gives Next.js's default error screen with no way back, no reference and no Sentry capture from the boundary.
- **Evidence:** `find web/app -name "error.tsx" -o -name "global-error.tsx"` returns nothing.
- **Fix:** add `web/app/global-error.tsx`, `web/app/(app)/error.tsx`, `web/app/(marketing)/error.tsx` and `web/app/(admin)/platform/error.tsx` built from `components/ui/error-state.tsx` ("Something went wrong", a "Try again" button calling `reset()`, a link home, the error `digest` as the reference), each calling `Sentry.captureException(error)` in an effect.
- **Done when:** a Playwright test that makes a page throw sees the designed error state in both themes with no axe violations.

### [x] C6.1.11 · P2 · The inline policy viewer reads the whole file into memory and its sandbox is a no-op — fixed in PR #154
- **Problem:** `view_file` (`api/app/modules/policies/own_router.py:105`) loads up to 25 MB into the API process for every view, so a few people opening a large policy at once can exhaust a worker. Its CSP says `sandbox allow-scripts allow-same-origin`, and MDN's `sandbox` documentation notes that this pair lets the framed document remove its own sandbox, so the directive adds nothing.
- **Evidence:** code read. The file types are limited to scanned PDF/JPEG/PNG and `default-src 'none'` blocks scripts, so there is no script risk today.
- **Fix:** stream the object (`StreamingResponse` over the boto3 body, read in chunks in a thread) instead of `storage.read`; drop `allow-same-origin` from the sandbox unless the browser PDF viewer test fails without it, in which case drop the `sandbox` directive and keep `default-src 'none'; frame-ancestors <web origin>`.
- **Done when:** the policy viewer e2e test still passes, and a unit test shows the route returns a streamed response.

### [x] C6.1.12 · P2 · The dashboard set-up list is not clickable and uses the browser's default progress bar — fixed in PR #153
- **Problem:** `web/components/dashboard/workspace.tsx:136` uses a native `<progress>` (dark green on grey, different in every browser) instead of `components/ui/progress.tsx`, and the five set-up steps are plain text, so "Add your company details" does not take you there.
- **Evidence:** code read and `docs/screenshots/phase-25/after/app-dashboard-light-1280.png`.
- **Fix:** replace `<progress>` with `<ProgressBar value={(done / total) * 100} label="Set-up progress" />`; give each checklist item an `href` (company profile, departments, new employee, Right to Work, key personnel) and render unfinished items as links with a chevron.
- **Done when:** the dashboard unit test checks each unfinished step links to its page; the screenshot shows the accent-coloured bar.

---

# Part 2 — Speed (what will make the app feel fast)

### [ ] O6.1.1 · P1 · B · Every public page is rendered on every request; nothing is cached
- **Problem:** `web/app/layout.tsx:33` calls `await connection()` in the root layout so the CSP nonce works. That turns off static generation and ISR for the **whole site**: the home page, pricing, all guides, 15 calculators and every sponsor-register profile are rebuilt per visit, and `export const revalidate = …` on the register pages does nothing. Next.js's own CSP guide (bundled at `web/node_modules/next/dist/docs/01-app/02-guides/content-security-policy.md`, "Static vs Dynamic Rendering with CSP") lists the cost: slower first load, no CDN caching, ISR disabled.
- **Fix:** split by route group. Keep the nonce and `connection()` for `(app)`, `(auth)` and `(admin)` (move the call into those layouts). For `(marketing)` use the hash-based CSP the same guide describes ("Subresource Integrity"): enable `experimental.sri` in `next.config.ts`, have `proxy.ts` send a nonce-free, hash-based `script-src` for marketing paths, and remove `connection()` from the root layout. Theme stamping on marketing pages moves to a small hashed inline theme script instead of reading the cookie on the server. Then let Cloudflare cache marketing HTML (`s-maxage` + `stale-while-revalidate`). The feature is marked experimental: if the build or the CSP tests do not hold, stop and record it with `bus.sh decide` instead of weakening the policy.
- **Done when:** `next build` output marks marketing routes as static or ISR; the pentest and CSP unit tests pass with no `'unsafe-inline'` in `script-src`; Lighthouse TTFB on the home page is recorded before and after.

### [x] O6.1.2 · P1 · Password hashing blocks the whole API worker while it runs — fixed in PR #156
- **Problem:** `verify_password`, `hash_password` and `spend_verification_time` (argon2id, 64 MB, 3 passes) are called directly inside `async` handlers (`auth/service.py:218-220`, `auth/router.py:240`, `auth/accounts.py`). Each call holds the event loop for its full duration, so one sign-in pauses every other request on that worker; a handful of concurrent sign-ins stall the API (4 workers).
- **Fix:** run them off the loop: `await asyncio.to_thread(verify_password, …)` at each call site (argon2-cffi releases the GIL while hashing). Add a module-level `asyncio.Semaphore(2)` around them so a login flood cannot take 64 MB × many threads.
- **Done when:** a test starts a slow fake hash and shows `/health` still answers meanwhile; auth tests pass.

### [x] O6.1.3 · P1 · Public sponsor search scans the whole register on every keystroke — fixed in PR #173
- **Problem:** `GET /public/register/explore?q=` (`api/app/modules/register/public.py:613`) and the in-app search (`search/router.py:66`, recruitment, documents, policies) use `ILIKE '%text%'` / `lower(x) LIKE '%text%'`. `pg_trgm` is installed (`alembic/versions/20261101_0001_foundations.py:23`) but only the SOC table has a trigram index, so these are full scans; the register one is public and unauthenticated.
- **Fix:** one migration adding GIN trigram indexes (`gin_trgm_ops`) on `register_sponsors.organisation_name` and `register_sponsors.town`, and expression indexes on `lower(first_name || ' ' || last_name)` for `employees` and `candidates` (PostgreSQL docs, pg_trgm: these serve `LIKE`/`ILIKE` with a leading wildcard). Debounce the explorer input by 250 ms and require 2+ characters in `web/components/register/explorer.tsx`.
- **Done when:** `EXPLAIN` of the explore query on the loaded register shows a bitmap index scan; `docs/data-model.md` regenerated; `check-rls` passes.

### [x] O6.1.4 · P2 · No code is loaded on demand — fixed in PR #161
- **Problem:** there is not one `next/dynamic` or `lazy()` in `web/` and 206 of 387 component files are client components, so heavy, rarely used pieces (command palette, QR code for MFA, org chart, rota grid, calculators) ship with the pages that merely contain them.
- **Fix:** load on first use with `next/dynamic`: `command-palette`, `shortcuts-sheet`, the `qrcode` import in MFA enrolment, the organogram canvas, the rota week grid. Record `next build` First Load JS per route before and after.
- **Done when:** First Load JS for `/dashboard` and `/` is lower in the build output and e2e still passes.

### [x] O6.1.5 · P2 · Each API request opens two database sessions and re-reads the same rows — fixed in PR #174
- **Problem:** `require()` (`api/app/modules/rbac/deps.py`) runs 4 to 5 queries on a global session (user, membership + company, terms version, terms acceptance) and then opens a second tenant session, for every request. The pool is 5 + 5 per worker (`db/engine.py`).
- **Fix:** cache the current terms version in process for 60 s; cache "user X accepted version V" in Redis after the first positive answer; combine membership, company and acceptance into one query. Do not cache membership status or role (they must take effect at once).
- **Done when:** a query-count test shows `require()` issues at most 2 statements on a warm cache; p95 of the list endpoints from T22.2 is re-measured and recorded.

### [x] O6.1.6 · P2 · Lists reload from scratch on every visit — fixed in PR #175
- **Problem:** pages fetch in `useEffect` (75 component files) with no shared client cache, so going back to a list shows the skeleton again and refetches.
- **Fix:** add a small stale-while-revalidate cache in `web/lib/api` keyed by path + query (show the last answer at once, refresh in the background, drop on sign-out or company switch), and use it in the list pages first (employees, leave, recruitment, documents). Prefetch a row's detail on hover/focus.
- **Done when:** navigating list → detail → back shows the list instantly in the journey e2e test, with a background refresh.

### [x] O6.1.7 · P2 · B · Front-door hardening that belongs with deployment (do with Phase 23) — fixed in PR #162
- **Problem / Fix:** (a) add `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Resource-Policy: same-site` to `baseSecurityHeaders` in `web/lib/security/csp.ts`; (b) Cloudflare: cache `/_next/static` for a year (immutable), enable Brotli and HTTP/3, add the WAF rate rule for `/api/v1/public/*` and `/api/v1/auth/*`; (c) require step-up before `POST /auth/platform-session` (`api/app/modules/rbac/platform_session.py`) so a stolen tenant session of a platform admin cannot open the admin site by itself.
- **Done when:** the header unit tests list the new headers; the platform-session test needs step-up; the Cloudflare items are ticked in `docs/runbooks`.

---

# Part 3 — UI: an Apple-quality "glass" look (owner goal)

What is there today (from the Phase 25 screenshots and `web/app/globals.css`): a clean, flat, Apple-inspired system. Glass exists only on the sidebar, toolbar, tab bar and sheets (`material-chrome`, `material-sheet`), and it sits on a flat grey (`#f5f5f7`) or pure black canvas, so there is nothing behind it to blur and it reads as solid. Cards are opaque. To look like current Apple design (Liquid Glass; Apple Human Interface Guidelines, "Materials") the product needs colour and depth **behind** the glass, a small family of materials, light on the edges, and motion; and it must stay readable (WCAG 2.2 AA, 4.5:1 for text) and fast.

### [x] U6.1.1 · P2 · B · Add the glass material tokens (the foundation every other UI item uses) — fixed in PR #163
- **Fix:** in `web/app/globals.css` add, for light and dark (and the duplicated dark block the token test keeps equal): `--glass-thin`, `--glass-regular`, `--glass-thick` (elevated surface at about 55%, 70%, 82% alpha), `--glass-stroke` (1 px inner edge: white at 60% in light, 14% in dark), `--glass-highlight` (top inner highlight), `--glass-shadow` (soft, wide, low alpha). Add utilities `material-glass-thin|regular|thick`: background + `backdrop-filter: saturate(180%) blur(24px)`, `box-shadow: inset 0 1px 0 var(--glass-highlight), 0 0 0 1px var(--glass-stroke), var(--glass-shadow)`. Keep the existing fallbacks: solid surface when `backdrop-filter` is unsupported or `prefers-reduced-transparency: reduce`, and add `@media (prefers-contrast: more)` → solid with a visible border. Extend `tests/unit/design/tokens.test.ts` so every text token still passes 4.5:1 on each glass tier composited over both the lightest and darkest backdrop colour.
- **Done when:** the token test passes; `/design` shows the three tiers in both themes.

### [x] U6.1.2 · P2 · B · Give the glass something to refract: an ambient backdrop — fixed in PR #164
- **Problem:** glass over a flat colour is invisible.
- **Fix:** add a fixed, non-interactive backdrop layer behind `(app)`, `(auth)` and marketing heroes: two or three large, very soft radial gradients in the brand accent and one neighbouring hue at low strength (about 10 to 14% in light, 18 to 22% in dark) over `--bg`, drawn with CSS only (no image, no JS), `position: fixed`, `pointer-events: none`, `contain: strict`. No animation by default; an optional slow drift only when `prefers-reduced-motion: no-preference`. Keep data-heavy areas (tables, forms) on calm ground: the gradient is strongest at the top corners and fades out by 40% of the viewport height.
- **Done when:** screenshots at 390 and 1280 in both themes show visible depth behind the toolbar and sidebar, axe reports no contrast failures, and Lighthouse performance is unchanged.

### [x] U6.1.3 · P2 · B · Make the app shell float — fixed in PR #165
- **Fix:** sidebar (`components/app/sidebar.tsx`), toolbar (`toolbar.tsx`) and mobile tab bar (`mobile-tab-bar.tsx`) move from edge-to-edge bars with a hairline to floating glass: 8 to 12 px inset from the window edge, `rounded-card` (pill shape for the tab bar on phones), `material-glass-regular`, content scrolling underneath. The toolbar turns from clear to glass only after the page scrolls. Fix the clipped last nav item above the user footer ("Rota" is cut in `app-dashboard-light-1280.png`): add a fade mask and bottom padding to the scrolling list.
- **Done when:** shell e2e and a11y specs pass; no content is hidden under the floating bars at 360, 390, 768 and 1280 (safe-area insets respected).

### [x] U6.1.4 · P2 · B · One card style, on glass — fixed in PR #166
- **Problem:** the dashboard mixes bordered cards ("Get set up", "Approvals") with borderless ones (the four KPI tiles); section cards are mostly empty space.
- **Fix:** `components/ui/card.tsx` and `kpi-card.tsx` get one look: `material-glass-thin`, no hard border, the inner edge highlight, `--radius-card`. Use solid `bg-elevated` only for dense data (tables, long forms) where glass would hurt reading. KPI tiles gain a small status line and an icon so a "0" is not the only content; empty cards show the existing `empty-state` with one action instead of blank space.
- **Done when:** the dashboard, employee detail and company pages use only the two card variants; screenshots updated.

### [x] U6.1.5 · P2 · Remove the doubled page title and fix the breadcrumb on detail pages — fixed in PR #159
- **Problem:** the toolbar shows "Dashboard" and the page shows "Dashboard" again directly under it (`app-dashboard-light-1280.png`); on a person's page the toolbar says "Employees" while the page is "Nadia Patel" (`app-employees-id-dark-1280.png`).
- **Fix:** Apple's large-title pattern: the page keeps the large title; the toolbar title is hidden until the large title scrolls out of view, then fades in (IntersectionObserver on the `h1`). The breadcrumb on detail pages ends with the record name ("People / Employees / Nadia Patel").
- **Done when:** unit test for the toolbar title visibility; e2e checks the breadcrumb on an employee page.

### [x] U6.1.6 · P2 · Tidy the action rows — fixed in PR #160
- **Problem:** dashboard quick actions are two rows of grey pills in two different sizes; the employee header mixes buttons and status chips in one row ("Print record", "Not recorded", "Resolve Right to Work", "Active"), so it is unclear what can be pressed.
- **Fix:** quick actions: one row, one size, each with its icon, the main one in the accent colour, overflow into a "More" menu on phones. Employee header: status chips sit under the name; actions sit together on the right with one primary button.
- **Done when:** screenshots at 390 and 1280; no wrap to a second row at 1280.

### [x] U6.1.7 · P2 · One accent everywhere — fixed in PR #158
- **Problem:** the brand accent is violet, but the plan chip ("1 year") is blue, avatars are pink and red, and the set-up bar is green.
- **Fix:** plan chip uses `accent-tint`/`accent-text`; avatars take a tint from a fixed 6-colour set derived from the accent hue (chosen by a hash of the name) with the same lightness in each theme; the progress bar uses the accent (C6.1.12). Status colours stay for status only.
- **Done when:** the design-audit page lists no non-token colours; contrast tests pass.

### [x] U6.1.8 · P2 · B · Give the marketing site something to look at — fixed in PR #167
- **Problem:** the home page (`public-light-1280.png`) is text and outlined boxes only: no product picture, an almost empty "Know what is due" panel, a flat lavender band, nothing that builds trust.
- **Fix:** hero: the ambient backdrop (U6.1.2) and a real product shot (the dashboard, in a glass window frame, light and dark variants, `next/image` with `priority` and fixed dimensions so nothing shifts). Feature cards on `material-glass-thin` with a hover lift. "Know what is due": a small reminder list that looks like the product instead of one line. Closing band: accent gradient with a glass call-to-action card. Add a short trust row (where data is kept, the security page, the free tools). Keep every claim true; no invented customer logos or figures.
- **Done when:** Lighthouse on `/` keeps LCP under 2.5 s and CLS under 0.1 on mobile; a11y spec passes; screenshots updated.

### [x] U6.1.9 · P2 · B · Motion and touch polish — fixed in PR #170
- **Fix:** sheets, popovers, the command palette and menus open with the existing spring (`--ease-spring`) from their trigger, with a scrim that blurs the page behind (off under reduced transparency); buttons and rows get a pressed state (scale 0.98, 80 ms); page changes use the View Transitions API for a short cross-fade where supported; list rows and cards fade and rise 8 px on first paint, staggered by 20 ms, never more than 200 ms in total. All of it off under `prefers-reduced-motion`. Limit blur to at most three stacked glass layers per screen and never animate `backdrop-filter` itself (it repaints every frame).
- **Done when:** `lib/motion.test.ts` covers the reduced-motion paths; a Playwright trace of opening the command palette on a throttled CPU shows no long frames.

---

## Notes (no action needed)
- Checked and found sound: tenant isolation (RLS on every `company_id` table plus automatic query scoping and write stamping), session handling (hashed tokens, rotation on sign-in/MFA/company switch, idle and absolute limits, per-request active-user and membership checks), the upload pipeline (extension, magic bytes, ClamAV fail-closed, attachment-only presigned links), Stripe webhook verification and idempotency, support mode (read-only by default, step-up routes unreachable), AI redaction, PDF rendering with resource fetching off, CSV formula escaping, host routing for the admin site, pinned and least-privilege CI.
- `pnpm audit --prod`: no known vulnerabilities. `ruff` and `mypy`: clean.
- Refund rule: a company can pay, cancel inside the 14 days for a full refund, and pay again, as often as it likes (`billing/service.py`: the cooling-off date restarts with each new subscription). This is the plan's rule as written, so it is not a bug, but the owner may want "one refund per company".
- A verification link also signs the person in (`POST /auth/verify-email`). It is single-use, lasts 24 hours, and two-step verification still applies, so it is acceptable; a 1-hour life would be tighter.
- The main checkout (`cmr_hr/`) has `changesneeded.md` deleted but not committed, and its `web/node_modules` is out of date (`@sentry/nextjs`, `@next/mdx`, `@mdx-js/mdx` are missing), which is why two web test files and the type-check could not load there. Neither is a code fault; run `pnpm install` in that folder.
- Not run in this audit: the browser (Playwright) suite, a production build, and the standalone `check-rls` command (the main checkout has no `.env`; the RLS drift tests inside the API suite passed). CI runs all three on the PR.
