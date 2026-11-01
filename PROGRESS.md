# PROGRESS

Build log for the platform described in [`plan.md`](plan.md). Tasks are done strictly in
order. After every task: tick it, add one line saying what was done and anything the owner
must do, and commit. Never record secret values in this file.

- **Last updated:** 2026-11-02
- **Current task:** T2.7 File pipeline

---

## Owner actions needed

### Blocking now

None.

### Coming up (not blocking yet)

Everything in Phases 0 to 22 runs locally. Nothing below needs doing until the phase shown,
unless a task notes otherwise here.

| Needed by | Owner action | Source |
|---|---|---|
| T0.8 | ~~Create the private GitHub repository~~ — done: `zohaib5911/hrcmr`, confirmed private. Still to do: (1) turn on **Settings → Security → Private vulnerability reporting** (referenced by `SECURITY.md`); (2) after the first green CI run, protect `main` under **Settings → Branches**: require a pull request and the one status check **CI passed**. I do not change GitHub settings myself. | plan T0.8, SECURITY.md |
| T23.1 | Set the repository **variable** `STAGING_URL` (Settings → Secrets and variables → Actions → *Variables*; it is a public URL, not a secret) so the weekly ZAP scan has a target. The GitHub *secrets* stay the three in deployment-requirements §6. | `.github/workflows/security.yml` |
| Anytime | Dependabot #3 (web dev dependencies: ESLint 9 to 10 and TypeScript) fails CI and is left open for you to decide. #1 (Redis 8) was rejected and Redis major updates are ignored; #2 (uv 0.13.6) was merged with the CI pin. | `.github/dependabot.yml` |
| Before launch | Give me the non-secret business details: brand name, domain, logo files (SVG lockup + mark, 512 px PNG favicon), accent colour, legal company name, number and registered office, ICO number, support email, sender address, confirm prices, Platform Admin emails, pixel and Companies House choices, optional office IPs. `brand.config.ts` currently holds the placeholder name "Brand". | deployment-requirements §1 |
| When I ask | Put **dev/test keys** in your own local `.env` (`cp .env.example .env`) and reply "the .env is ready": a low-limit `ANTHROPIC_API_KEY` (T14.4), Stripe **test** key and `stripe listen` webhook secret (T16.1), optional `COMPANIES_HOUSE_API_KEY` (T4.1). Turnstile uses Cloudflare's public always-pass test keys locally. | deployment-requirements §7 |
| T13.2 | Review the 8 original courses. | plan T13.2 |
| T15.2 | Review the rules-data diff and approve publishing rules v1. | plan T15.2 |
| T18.2 | Have a UK solicitor review the draft legal pages; remove the "DRAFT" labels only when you tell me to. | plan T18.2, §12 |
| T18.4 | Approve each comparison page (prices verified, date and source shown) before it is published. | plan T18.4 |
| T23.1 | Create the accounts in deployment-requirements §2, generate the secrets in §3 yourself, and set the variables in §4 and the GitHub secrets in §6 **directly in the dashboards**. Log in to Railway yourself (`railway login`) or export `RAILWAY_TOKEN` in your shell; never type it in chat. | deployment-requirements §2–6, §8 |
| T23.8 | Switch Stripe to live keys (you set them), and submit the sitemap in Google Search Console. | plan T23.8 |
| T24.1 | Confirm the 2027 Temporary Shortage List status on GOV.UK, check the calculator rates list, review the final Design QA screenshots, and store `backup-private.key` and `FIELD_ENCRYPTION_KEYS` in your password manager plus an offline copy. | plan §12, deployment-requirements §9 |

---

## UNVERIFIED figures

None recorded yet. Any rate, threshold or rule I cannot verify from an official source is
marked `UNVERIFIED` and listed here with its location.

---

## Decisions and interpretations

1. **Spec files** `plan.md` and `deployment-requirements.txt` live at the repository root as the build specification.
2. **Layout (T0.1):** all directories in plan section 3 exist and are kept in git with `.gitkeep`. Files that belong to a later task are created by that task, so no empty placeholder files exist: `.env.example`, `.gitleaks.toml`, `.pre-commit-config.yaml` (T0.2), `docker-compose.yml` (T0.3), `web/middleware.ts` (T0.6), `web/lib/permissions.ts` (RBAC tasks), `docs/data-model.md` (generated from models), `docs/security.md` (T21.2), `docs/runbooks/*` (T2.2 and T23.6).
3. **T19.2–T19.15** are expanded below into one task per row 1–14 of plan section 10, in the order listed. Row 15 (the Sponsorship Job Checker) is T15.8.
4. **Commits and pushes:** one commit per task, using Conventional Commits with the task id. On 2026-11-01 the owner created the private repo `https://github.com/zohaib5911/hrcmr.git` (remote `origin`, branch `main`) and authorised me to push to it. I push after each task commit, and to no other remote.
5. **Logo files:** `brand.config.ts` points at `/brand/logo.svg`, `/brand/mark.svg` and `/brand/favicon-512.png`. Neutral default assets are created in the web tasks and replaced by yours.
6. **Guard-rails (T0.2):** `pre-commit` is installed user-level with `uv tool install pre-commit`; it builds its own pinned `gitleaks` and `prettier`. The `eslint (web)` hook runs only when web source files are staged and needs `pnpm` (arrives in T0.6). `scan-bundle` is deliberately strict: even a bare `sk_live`/`whsec_` prefix in browser code fails, and a missing build directory fails (exit 2) rather than passing silently. Test fixtures assemble fake keys at run time so gitleaks never needs an exception.
7. **`.env.example`** holds names only, as the plan requires. Local-dev defaults (for example the model ids) live in the code's settings, not in the file.
8. **MinIO replaced by RustFS (T0.3), approved by the owner 2026-11-01.** The plan named MinIO as the local R2 stand-in, but `minio/minio` and `minio/mc` are gone from Docker Hub and the GitHub repo is archived ("no longer maintained", last release Oct 2025). RustFS 1.0.4 (Apache-2.0) is used instead; the bucket is still `files-dev`. This affects local development and tests only. Production is still Cloudflare R2. Fallbacks if RustFS misbehaves: SeaweedFS, then Versity S3 Gateway. Verified on 2026-11-01 with boto3 (the client the API will use): presigned 60-second GET URLs return `Content-Disposition: attachment`, tampered and expired URLs are refused with 403, anonymous and wrong-credential access is refused, and a 12 MB multipart upload round-trips intact. No fallback needed.
9. **Compose plugin:** `docker compose` was missing, so I installed v5.6.1 under `~/.docker/cli-plugins/` after checking its SHA-256 against the release's `checksums.txt`. Delete that one file to undo.
10. **For T2.7:** newer AWS SDKs add checksum headers that R2 and most S3 clones reject. Configure the S3 client with request/response checksums `when_required`; `rustfs-init` already sets this.
11. **API conventions (T0.4):** `APP_ENV` accepts `local` and `test` as well as `staging` and `production` (the deployment file lists only the last two). It has no default, so a forgotten value fails fast instead of silently running with local settings. OpenAPI and docs are served only for `local` and `test`; deployed environments get them through the super-admin API (Phase 17). Routes live under `/api/v1`, so the uptime monitor URL is `/api/v1/ready`.
12. **Logging (T0.4):** keys matching the plan's sensitive list are *dropped*, as the plan says, and that pattern includes the word `token`. When T14.4 logs AI usage, name the fields so they do not contain `token` (for example `usage_in` and `usage_out`) or they will vanish. `httpx` and `httpcore` log at WARNING because they print request URLs, which can carry tokens.
13. **Not done in T0.4 on purpose:** CORS and CSRF arrive with the auth tasks (T2.3, T2.4); trusting `X-Forwarded-For` behind Railway and Cloudflare is decided with rate limiting (T2.3); a script that generates a complete local `.env` will be added when something needs a running API with real settings (the first end-to-end test).
14. **Roles and provisioning (T0.5):** `provision-db` needs a *superuser* URL in `DATABASE_URL_ADMIN`, supplied only for that command and deliberately not part of the API's settings. It takes role names and passwords from `DATABASE_URL_OWNER` and `DATABASE_URL`, so no new variables are needed. Roles are cluster-wide, so one database cluster serves one set of passwords. For T23.2 I will run it through the owner's Railway session; the owner never has to paste a password. Grants are explicit per table (no default privileges), so the runtime role gets only what each migration gives it.
15. **RLS design (T0.5):** `ENABLE`, not `FORCE`, so migrations and `pg_dump` backups (T23.6) work as `app_owner`. The policy reads the company through `app_current_company_id()` with `NULLIF(..., '')`, because after a transaction the setting is an empty string and a bare `::uuid` cast would raise instead of failing closed. The `app_user` role has `statement_timeout` 60 s and `idle_in_transaction_session_timeout` 30 s; the report and export jobs (T10.2, T16.4) must stay under that or use their own role setting. RLS stops missing filters and bugs, not injected SQL (the setting can be changed by whoever runs arbitrary SQL), which is why a test confines raw SQL to `app/db/`.
16. **Views, materialised views, SECURITY DEFINER (T0.5, important for later phases):** a plain view runs as its owner and showed another company's rows in testing. Every view over tenant data must come from `create_tenant_view` (`security_invoker`). **This affects T7.1 (Right to Work derived-status view) and T8.2 (`leave_balances`).** Materialised views and `SECURITY DEFINER` functions are rejected by `check-rls`. Anything that must read across companies before sign-in (for example looking up a person's memberships at login, T2.4) must be designed around that: global tables, not a definer function. The super-admin role (T17) will get an explicit `TO platform_admin_rw` policy rather than BYPASSRLS.
17. **Tests use a disposable database (T0.5):** a `postgres-test` service (port 5433, in memory) joins the compose stack, because the DB tests create and re-password the cluster-wide roles and must never touch your development database. `created_by`/`updated_by` have no foreign key, and `company_id` gets its foreign key to `companies` in T2.1.
18. **Local `.env` still not generated:** the dev database `app` is not provisioned yet, and nothing needs it. When the first end-to-end test needs a running API with real settings, I will add the script that generates a complete local `.env` (random local secrets, never printed) and provisions the dev database.
19. **`proxy.ts`, not `middleware.ts` (T0.6):** Next.js 16 renamed the convention (`middleware` is deprecated); same function, new name. The admin pages live under an internal `/platform` segment because route groups do not appear in URLs and `(admin)` and `(app)` would otherwise collide; the proxy maps `admin.DOMAIN/x` onto `/platform/x`.
20. **Decision for you, later: strict CSP versus caching (T0.6).** A per-request nonce, which the plan requires, forces every page to be rendered on each request (Next.js docs: no static generation, no ISR, no CDN caching, no Partial Prerendering). That is right for the app and back office. It conflicts with the roughly 128,000 ISR-cached sponsor pages (T20.4) and with the Lighthouse 95 target for marketing pages (T18.3). Options when we get there: keep nonces everywhere and accept the server load; give the public pages Next's experimental hash-based SRI policy (static pages stay strict); or allow `unsafe-inline` scripts on public pages only. I will raise it again at T18.3 with measurements.
21. **Versions and supply chain (T0.6):** pnpm 10.34.7 (via Corepack), with `minimumReleaseAge` of 14 days so freshly published, possibly compromised releases are refused, and install scripts blocked. TypeScript 5.9 and ESLint 9, not the newest majors: TypeScript 7 is a rewrite the Next tooling does not yet target, and ESLint 10 leaves three plugins in `eslint-config-next` with unmet peer ranges. pnpm reports ESLint 9 as "no longer supported"; it is a dev-only tool, and I will move to 10 when the plugins do. `pnpm audit` has one moderate advisory (minimatch, reached only through ESLint, never shipped); production audit is clean.
22. **Rewrite origin bug (T0.6):** the admin-host rewrite initially returned 404 because Next.js compares a rewrite's origin with the address the server is bound to, and treats a mismatch as an external proxy. The proxy now resolves the destination against `request.url` and the server must bind `0.0.0.0` (documented in `proxy.ts`, the README and the Dockerfile). On a mismatch the failure is a 500, so admin pages are never exposed. For Railway (T23.1): make sure the web service's `HOSTNAME` is `0.0.0.0`, because the platform may set its own.
23. **shadcn/ui (T0.6):** initialised with the `radix` base and the Nova preset, which T1.1 replaces with the plan's tokens. I changed what its CLI generated: the `cn` helper is the standard `clsx` + `tailwind-merge` pair, not the brand-new pre-1.0 `cn` package it wired in; its 637 lines of plain CSS (`shadcn/tailwind.css`) are vendored as `app/shadcn-tailwind.css` so the `shadcn` CLI and its 224 packages are not a run-time dependency; and its Google-font (Geist) change to `layout.tsx` was reverted, because fonts are T1.1 (Inter, self-hosted). `next dev` also writes a small `web/AGENTS.md` pointing at the bundled docs; it is committed. Playwright browsers are not installed yet (the header tests need none); T1.x installs them for screenshots and axe.
24. **API contract (T0.7):** the OpenAPI document is generated from the running code, never hand-written. CI (T0.8) must run `pnpm gen:api:check` from `web/` and the e2e job needs `uv` and the compose services. Error responses are documented once, globally, as `4XX`/`5XX` → `ErrorEnvelope`.
25. **CI design (T0.8):** `ci.yml` has ten jobs and one gate job, **CI passed**, which is the only check branch protection needs. Every third-party action is pinned to a commit SHA (tag in the comment) and every scanner (gitleaks, Semgrep, Trivy, actionlint, zizmor, ZAP) runs as a container pinned by digest, because a moved tag is the usual way a pipeline gets compromised. Nothing is cached, so a poisoned cache cannot reach a later run. The token is read-only, there are no secrets in `ci.yml`, and `persist-credentials` is off. Dependabot cannot see the digests in the workflow `env:` blocks, so they are refreshed by hand about monthly. Semgrep's rule packs are fetched from semgrep.dev at run time, so a newly published rule can turn CI red on code that did not change; that is intended, and the fix is to fix the code or add a `nosemgrep: <rule-id>` with a reason.
26. **14-day cooldown for Python too (T0.8):** a Semgrep rule showed that only the web side refused brand-new releases. `api/pyproject.toml` now has `exclude-newer = "14 days"`. Re-locking moved 15 packages back (FastAPI 0.162 → 0.146, Starlette 1.10 → 1.8, Pydantic 2.14.2 → 2.14.1, SQLAlchemy 2.1.6 → 2.1.5, and so on) and **ruff 0.17.3 → 0.17.1**, in `pyproject.toml` and the pre-commit hook. All 172 API tests, ruff, `mypy --strict` and the generated API types were unchanged. The cooldown had one real cost: it pulled `certifi` back to a version with a known vulnerability (PYSEC-2026-4320), so that one package has an explicit exception (`exclude-newer-package`), to be removed after 2026-11-06. Rule: a cooldown never holds back a security fix.
27. **Web image has no npm (T0.8):** Trivy found HIGH vulnerabilities (undici, brace-expansion) in the copy of npm that the Node base image bundles. The app runs `node web/server.js` and never uses npm, so the runtime stage now deletes npm, npx, corepack and yarn. The vulnerable code is gone rather than ignored, the image is smaller, and an attacker who gets a shell has no package manager. Re-checked: the hardened container (read-only, no capabilities, uid 10001) still serves pages and the admin host.
28. **ZAP baseline (T0.8):** the weekly scan runs only against staging (https, a `staging` label in the host) and skips with a warning until `STAGING_URL` is set. A dry run against the production web container found a real gap: static files, `/healthz` and the favicon skip the proxy and had no `Permissions-Policy`. Fixed in `next.config.ts` with a test; the dry run now reports 0 failures. Three warnings are accepted on purpose: *Non-Storable Content* (pages carry a per-request nonce, so they cannot be cached; see decision 20), *Cross-Origin-Embedder-Policy* (enabling it would break the Stripe and Turnstile frames), and the informational *Modern Web Application*.
29. **Semgrep triage (T0.8):** six findings on first run. Two were removed by changing the code rather than silencing it (the migration now lists its five `CREATE EXTENSION` statements literally; `provision.py` passes values as one `VARIADIC text[]` parameter so its SQL is a constant). One is the cooldown above. One module that builds regexes from its own constant list carries a single `nosemgrep` with the reason. Dev-only `pnpm audit` currently shows 3 moderate advisories (reachable only through ESLint); the CI bar for dev tools is *high*, for production *moderate*.
30. **Colour tokens against WCAG AA (T1.1):** the plan asks for its exact colours *and* for every pair to pass AA, and a few of its colours do not. I computed every text and control pair in both themes and changed only what failed, by the smallest step: light `--success` #248A3D → #1F7835, `--warning` #B25000 → #AC4D00, `--danger` #D70015 → #CC0014, `--info` #0071E3 → #0062C6 (its fill keeps #0071E3), and dark `--danger` text #FF453A → #FF4B40 (its fill keeps #FF453A). Tokens the plan does not list but needs: `--accent-text` (links: the accent itself is 4.3:1 on the canvas), `--on-accent` (label on a filled button: white on light, **black on dark**, because white on the dark accent is only 3.0:1), `--placeholder` (#636366; the secondary label is 4.0:1 on an input fill), and `-fill` and `-tint` for each status colour. Every difference is listed in `tests/support/expected-tokens.ts`, which tests compare with the stylesheet, so no other plan value can drift. Rules for later tasks: `--label-tertiary` is 3.3 to 3.6:1, so only for large text and icons, as the plan says; status fills (#34C759 and the like) are under 3:1 on white, so a fill is never the only indicator and always sits with a text label (plan 5.11); an input's grey fill is almost invisible against a card (about 1.1:1), so T1.2's inputs need a visible label and a focus ring, not the fill alone.
31. **How themes are written (T1.1):** dark is written out twice, for the system setting and for `data-theme="dark"`, and a test fails if the two differ. CSS `light-dark()` would avoid the duplication but renders no colour at all on Safari before 17.5 and Chrome before 123, which Next.js's own default browser targets still include. Every token, derived ones included, is declared in full in each theme block, so a nested `data-theme` scope (the `/design` page uses them) resolves correctly. Tailwind's default colour palette is switched off (`--color-*: initial`): a component can only use a design token.
32. **`/design` is development-only by construction (T1.1):** the first version called `notFound()` in production, which returned 404 but still streamed the page's title ("Design tokens") in the response body. The file is now `app/design/page.dev.tsx` and `pageExtensions` in `next.config.ts` enables `dev.tsx` only outside production, so the route is never compiled into a production build. A test checks the build output has no design route and that the 404 body says nothing about it.
33. **Fonts (T1.1):** Inter comes from the `@fontsource-variable/inter` package (SIL Open Font License) through `next/font/local`, so nothing is fetched from Google at build or run time, and the package is covered by the lockfile and the 14-day release rule. The Latin file (48 KB) is preloaded; the Latin Extended file loads only when a page contains a letter from it (Polish, Romanian, Turkish and similar names, common in UK workforces). The system font stays first in the stack, so Apple devices show their own. The font variables carry fallbacks, so a missing variable can never blank the whole font stack.
34. **Theme cookie and brand accent (T1.1):** the choice is a `theme` cookie (`light` or `dark`; no cookie means follow the system), read by the root layout and stamped on `<html>` on the server: no flash and no inline script. It is a preference, not a secret; it is `SameSite=Lax`, `Secure` on https, and any other value is ignored. The brand accent reaches the page as a `<style nonce>` element, because an inline `style=""` attribute would be blocked by the Content-Security-Policy. `brandAccentCss` accepts only `#rrggbb`, so configuration cannot inject CSS, and refuses colours that would fail AA, so editing `brand.config.ts` later cannot make buttons or links unreadable.
35. **Browser tests (T1.1):** Chromium is installed locally (`pnpm exec playwright install chromium`, about 120 MB) and in CI (`--with-deps`). Playwright has two projects: `production` (as before) and `design`, which runs against `next dev` on port 3101. The design project addresses the server as `localhost`, because Next.js blocks its dev resources for any other origin, which left the page unhydrated under `127.0.0.1`. Colours shown on `/design` are read from the browser, because the CSS build rewrites `#000000` to `#000` and `rgba()` to 8-digit hex.
36. **Scope of T1.2 (T1.2):** plan T1.2 says "every component in 5.7". Built: everything generic. Not built, because another task owns it and building it now would duplicate it or guess at its data: **CommandPalette and KeyboardShortcutsSheet** (T1.4 names them), **AskMadyPanel** (needs the streaming API, T14.4), **OrgChart canvas** (T12.2), **WeekGrid** (rota semantics, T9.5), **Charts** (Recharts is built when the first real chart needs it, T14.1, so the wrapper is tested with real data). `CalendarMonth` is built now because the date pickers need it.
37. **No inline styles anywhere (T1.2):** the Content-Security-Policy (no `unsafe-inline` for styles) blocks `style=""` in server-rendered HTML, which the dev server's looser CSP hides. A first `ProgressBar` used `style={{ width }}` and would have rendered empty in production. ESLint now forbids the `style` prop (`react/forbid-dom-props`), and the same constraint shaped other components: the progress bar and ring are SVG attributes, the virtualised table pads with spacer rows (a `height` attribute), the text area grows by setting its height through the DOM, and the brand accent is a `<style nonce>` element.
38. **`cn()` knows the design system (T1.2):** stock `tailwind-merge` read `text-callout` as a text colour and removed the real colour (`text-on-accent`) as a conflict, so every filled button had a black label and every hint was the wrong size. `lib/utils.ts` declares the type scale, radii and shadows to it, a test pins it (and shows stock behaviour is wrong), and a second test fails on any class from the disabled default palette (a `bg-white` switch thumb was invisible; `--knob` is now a token).
39. **More tokens and contrast rules (T1.2):** added `--accent-tint` (soft accent fill), `--scrim` (backdrop) and `--knob` (switch thumb), and darkened the derived link colour `--accent-text` from 12% to 15% black so link text passes on the accent tint (4.67:1 or better). The brand-colour guard now also checks that tint. Rules found by axe and recorded in the README: no `text-label-secondary` on the grey fill (4.1 to 4.4:1); drop zones sit on the elevated surface; selected radio cards use a ring, not a tint; a tinted button inside a coloured alert fails in dark mode, so alerts use gray or filled buttons; a tinted button's hover is a ring, because a heavier tint fails in dark mode.
40. **Motion and hydration (T1.2):** `SegmentedControl` first left out its sliding highlight when `prefers-reduced-motion` was set. The server cannot know that, so the HTML differed from what the browser built and React reported a hydration mismatch, for exactly the users who set that preference. The element is now always rendered and only its transition changes. Rule: markup must never depend on a motion or colour-scheme preference. Radix radio groups choose the radio an arrow key moves to, but on a timer after the key goes down; a person holds a key long enough, Playwright's instant press does not, so tests press arrows with a short hold (`pressArrow`). (I first misread this as a Next.js ordering bug, wrote a workaround, found by logging that it was not, and removed it.)
41. **How accessibility is tested (T1.2):** axe runs with every WCAG 2.2 A/AA and best-practice rule. A small, named set of "needs review" results is accepted and each is explained in `tests/e2e/design-a11y.spec.ts`: contrast over translucent materials and over a deliberate gradient, an empty input (no text yet), a one-character unit, text another layer covers, everything behind an open modal (Radix hides it and traps focus), portals outside `<main>`, and a popover trigger's `aria-controls`. The colour pairs behind them are covered by the token tests. A hydration marker (`html[data-hydrated]`, development page only) lets tests wait for the page to be interactive instead of guessing; a tooltip closes when anything scrolls, so tests scroll first.
42. **Dependencies added (T1.2):** `motion` 14.3.0 (Framer Motion's successor package; used for the segmented control and KPI count-up), `@tanstack/react-virtual` 3.14 (row windowing). TanStack Table 9 was installed and then removed: it is a ground-up redesign with a store dependency, and sorting, selection, column visibility and paging are a small amount of code with full control of the markup and accessibility. Dev only: `@axe-core/playwright`, `jsdom`, Testing Library. All are at least 14 days old by the lockfile rule, and `pnpm audit` is clean. The `radix-ui` umbrella package provides every primitive.
43. **Dates, numbers and tables (T1.2):** dates are ISO strings; arithmetic is on UTC calendar days so the clocks changing cannot move a date; weeks start on Monday; typed dates are read day-first ("3/4/2026" is 3 April), a two-digit year of 70 or more is the 1900s (dates of birth) and below that the 2000s, and nothing is guessed (31 Feb is refused). Date-times are shown in UK time whatever the visitor's zone, so the server and browser print the same text. Table exports defuse spreadsheet formulas (a cell starting `=`, `+`, `-`, `@` gets a leading apostrophe), because an employee named `=HYPERLINK(...)` would otherwise attack whoever opens the file. On a phone the table is a list of cards and pages (a thousand cards drawn at once took 40 s to scan). Focus returns to the text box, not the calendar icon, after choosing a date.
44. **The sidebar's contents are my reading of the specification (T1.3):** the plan gives the six groups (Overview, People, Compliance, Time, Me, Company) but not each row, so the 21 rows come from the module sections. **Compliance** holds the sponsor hub, Sponsored employees, Reminders, the Sponsorship checker, Documents, Policies and Reports (the plan files documents, policies and reports together in 8.10); change of circumstances and the dossier are reached from the hub's tool cards, not the sidebar. **Me** is My profile and My documents (My leave, shifts and learning live as tabs inside Leave, Rota and Learning). **Company** is the overview, User access and Billing; the other company settings are pages under `/company` built in Phase 4. Routes not named in the plan (`/reports`, `/profile`, `/my-documents`, `/company/users`) are mine and are one line each to change in `lib/navigation.ts`. Hiding rows a role may not see is T3.4.
45. **Honest placeholders in the shell (T1.3):** with no session yet, the company switcher and user card show loading placeholders rather than invented names, and the badge counts and bell are empty rather than made up. The bell's empty state is a real state. Two controls announce events for features that arrive in T1.4: the search box says "open the command palette" and the help button says "open the shortcuts sheet" (`lib/shell-events.ts`); nothing listens yet, and T1.4 does. There is no Sign out until the API can sign out (T2.4, T3.4). The company switcher lists the person's companies but only the current one is selectable until switching exists. `MenuItem` can no longer take `asChild`: its icon and label wrappers give Radix two children, which crashes at run time and was invisible to the type checker.
46. **Sidebar state and the `[` key (T1.3):** the collapsed choice is a cookie (`sidebar=collapsed`) read by the layout, so the server draws the right width and nothing animates on load; it follows the theme cookie's pattern. `[` toggles it from a window listener that ignores repeats, modifier keys and any text field. T1.4 builds the global shortcut handler and should fold this into it.
47. **Responsive rules found by testing (T1.3):** the sidebar is a fixed 260/72 px column from 768 px, and phones get the tab bar instead (every target at least 44 px, safe-area padding). The toolbar's wide search box needs 1024 px; between 768 and 1023 px only 508 px is left beside the sidebar, which made the page scroll sideways by 52 px until the search became an icon there. The page content has bottom padding for the tab bar, and a "Skip to content" link is the first Tab stop.
48. **Screenshots on request (T1.3):** `tests/e2e/shell-screenshots.spec.ts` runs only with `SCREENSHOTS=1`, so ordinary runs never rewrite the images committed in `docs/screenshots/phase-1/`. The shell tests run against the production build (the signed-in routes are part of it), not the development server.
49. **Public-site links and cookies (T1.5):** the nav in `web/lib/marketing-nav.ts` names the pages T18 builds (the sponsor page is `/sponsor-licence-compliance` because `/sponsor-compliance` is the app's); until they exist the links do not prefetch, and T18.1 must remove `prefetch={false}` and test that every link resolves. Pricing amounts are never in code: `PricingCards` and `HeadcountSlider` take them as props (shown with the plan's figures on the dev-only `/design/marketing`). Marketing pixels are not loaded yet; they must wait for `brand.cookieConsent.marketing` and the `brand:cookie-consent-changed` event.
50. **Playwright output folder (Phase 1 gate):** reports go to `.playwright-results/` outside `web/`, because `next dev` watches `web/` and a failing test writing there reloaded every page in the design tests (the cause of earlier mass timeouts). `style-src-attr 'unsafe-inline'` is an accepted exception: see `docs/security.md`.
51. **Identity tables and tenancy (T2.1):** `sessions` and `invitations` have a `company_id` but are found by a cookie or an emailed link before any company is known, so they have no tenant policy and are listed in `PRE_TENANT_TABLES` (`app/db/rls.py`); only the auth service may touch them, through `GlobalSession`, filtering by token hash. `memberships` has the tenant policy plus `own_memberships` (a person reads their own rows through the new `app.user_id` setting, which `GlobalSession(user_id=...)` and `TenantSession` now set), so sign-in can list their companies. `companies` and `users` have no policy for the same reason; they are read through a membership. Company lists and the public careers slug lookup (T11) will need a deliberate path, not a loophole. The company purge in Phase 16 has to delete audit rows, which the trigger forbids: it will need its own, audited, owner-only route. `mfa_secret` is plain text until T2.2 swaps in `EncryptedString`.
52. **Auth design (T2.3):** the lockout state (failed count, lock) lives in Redis keyed by a hash of the e-mail address, not on the user row, so an address with no account locks and answers identically to a real one (the row also records it, for support). The common-password list holds only the NCSC entries of 12 characters or more, because shorter ones fail the length rule anyway (`app/modules/auth/data/SOURCE.md`). Recovery codes use a keyed fast hash, because each has 50 random bits. Webhooks are exempt from CSRF by path (`/api/v1/webhooks/`) and must verify their own signature (T16.1).
53. **Endpoint choices (T2.4):** signing up does not sign anyone in: the verification link does (plan 8.1). A person who already has an account and is invited is added to the company but must sign in as usual, so an invitation can never be used to take over an account. `POST /auth/login` picks the company itself when there is exactly one, otherwise the client calls `/auth/switch-company`. `Turnstile` is skipped only when no secret key is set, which deployed environments cannot do. Until T2.8 the `Mailer` logs only that a message of a kind was requested.
54. **RBAC choices (T2.5):** a permission with no scope in its name (`employee.profile.read`) is asked for by that name, and `require` reports the widest reach the role has: company-wide, `_reports` or `_own`. The endpoint, not `require`, limits what it returns (`access.can_reach(employee_id)`). The reports query names the `employees` columns directly; Phase 4's table must have `reporting_authority_employee_id` and `leave_sanctioning_employee_id`. The Auditor's company-wide reads follow the plan's list of areas literally, so attendance and document reads are not among them (say if that is wrong). Employees hold `attendance.record.write_own` and `employee.profile.write_own` as the plan says; the attendance and profile endpoints must accept only clock in/out and contact, address and emergency-contact fields.
55. **Audit trail is permanent (T2.6):** even the owner role cannot truncate `audit_events`, so tests never empty it; they ask about the companies they created. The company purge (Phase 16) will need an audited, owner-only route for it. Events with no company are for the platform and need the admin API (T17), which the tenant policy hides from every company.

---

## Environment notes

Checked 2026-11-01 on the build machine: git 2.56, Node 24.21, Python 3.14.8 (the plan needs **3.12**, which I will provision with `uv`), uv 0.12, Docker 29.9. `pnpm` is not installed; I will enable it via Corepack in T0.6.

---

## Phase summaries

Written at each phase gate, with screenshots in `docs/screenshots/<phase>/`.

### Phase 0 — Foundations and guard-rails — gate passed 2026-11-01

**What exists.** A monorepo with a private GitHub remote; a one-command local stack (Postgres 16 with pgvector, a disposable test Postgres, Redis, RustFS for R2, Mailpit, ClamAV, Stripe CLI on request); a FastAPI service (settings that fail closed, JSON logging with secret redaction, request ids, one error envelope, health and readiness); a database layer in which the **database itself** confines every tenant table to one company (Row-Level Security, two non-bypass roles, a session that sets the company per transaction, drift checks for views and functions); a Next.js 16 app with host routing, a per-request nonce CSP and the section 4.6 headers; a typed API client generated from the API's own OpenAPI document; secret guard-rails at commit time, in the build and in CI; and the CI, security-scan and Dependabot setup.

**Regression, on the commit that CI ran (`b4be559`, run 41323265569, all 11 jobs green):** API 172 tests; web 113 unit tests; 32 guard-script tests; 29 Playwright tests (security headers, host routing, a real typed call to a live API). `ruff`, `mypy --strict`, ESLint and `tsc --strict` are clean. Both container images pass Trivy (no fixable HIGH or CRITICAL findings) and run hardened (read-only filesystem, no capabilities, uid 10001). `pip-audit` and production `pnpm audit` report nothing. A ZAP baseline against the production web container reports 0 failures.

**Security properties proved by tests that fail when the property is broken** (each by deliberately breaking the code and watching the suite go red): company A cannot read, change, delete, insert or move company B's rows even with raw SQL as the application role; the admin pages are a 404 on the main host (including 20 odd or encoded paths); every page carries a fresh CSP nonce and no `unsafe-inline`; secrets and the key-like words in the plan's list never reach the logs; no `NEXT_PUBLIC_*` name outside the allowlist exists; a fake secret fails the commit hook and the CI secret scan.

**Screenshots.** None for this phase: it has no designed UI (T1.1 onward does).

**Decisions and risks to remember** (details above): decision 16 (views must be `security_invoker`; affects T7.1 and T8.2); decision 20 (nonce CSP against cached pages, to be raised at T18.3 and T20.4); decision 22 (the web server must bind `0.0.0.0`; check `HOSTNAME` on Railway at T23.1); decision 26 (14-day cooldown; remove the `certifi` exception after 2026-11-06); decision 12 (never name a log field with `token` in it).

**Open at the gate (none block Phase 1):** protect `main` and enable private vulnerability reporting (yours); decide on Dependabot PRs #1 and #2; the fake-secret check as a real GitHub PR (needs your go-ahead); no local `.env` generator yet (written when the first end-to-end test needs real settings).

---

### Phase 1 — Design system and app shell — gate passed 2026-11-02

**What exists.** Design tokens and theming (light/dark, system), a primitive component library with a `/design` page (dev only), the signed-in app shell with 21 empty pages, the ⌘/Ctrl+K palette and `?` shortcuts sheet with every shortcut from plan 8.19, and the public-site frame (header, footer, section components, cookie consent).

**Regression, whole suite once:** web 711 unit tests; 254 Playwright tests (production build and dev server, 0 failed, 0 skipped); API 172 tests; `tsc`, ESLint and `ruff`/`mypy` clean. CI ran green on T1.3; T1.4 and T1.5 are pushed with this gate.

**Screenshots.** `docs/screenshots/phase-1/`: the shell, the palette and shortcuts sheet, the public home page (4 widths, light and dark), cookie banner, cookie settings and phone menu. The 20 other signed-in pages are the same empty-state template inside the shell; they get their own shots when their content is built.

**Open at the gate:** the pages the marketing nav links to (T18); Dependabot #3 (ESLint 10 and TypeScript, CI red) is left open.

---

## Task list

### Phase 0 — Foundations and guard-rails
- [x] **T0.1** Repo initialisation — 2026-11-01. `git init -b main`; full Section 3 directory tree; README, SECURITY, PROGRESS (all 145 task ids, checked against plan.md by script), `.gitignore`, `.editorconfig`, `brand.config.ts`, `docs/architecture.md`. Owner: none.
- [x] **T0.2** Secret guard-rails before any code — 2026-11-01. `.gitleaks.toml` (default ruleset + 7 project rules), `.pre-commit-config.yaml` (gitleaks, ruff, ruff-format, prettier, eslint, plus detect-private-key and the NEXT_PUBLIC allowlist), `.env.example` (53 names, values empty; a test keeps it identical to deployment-requirements §4), `scripts/check-public-env.mjs`, `scripts/scan-bundle.mjs`, 32 unit tests. Proved in a throwaway clone: a fake `sk_live_` key and 6 other leak types are blocked (output redacted), a clean commit passes, `git check-ignore .env` → ignored; gitleaks finds nothing in the tree or history. Owner: none.
- [x] **T0.3** Local stack (Docker Compose) — 2026-11-01. `docker-compose.yml`: postgres+pgvector 0.8.7/pg16, redis 7.4, RustFS 1.0.4 (+ one-shot `files-dev` bucket job), mailpit 1.33, clamav 1.5.4, stripe-cli under profile `stripe`; every port bound to 127.0.0.1; healthchecks and named volumes; README section. Verified by running it: `docker compose up -d --wait` exits 0 (about 11 s warm) with all services healthy; Postgres 16.15 creates pgcrypto, pg_trgm, unaccent, vector and citext and runs a pgvector query; Redis answers with AOF on; RustFS passed 14 S3 checks; Mailpit round-trips an SMTP message; ClamAV detects EICAR (plain, in 7-byte chunks, and inside a ZIP) and passes clean data; Postgres, Redis and bucket data survive `down`/`up`; the Stripe CLI exits with a clear message when no key is set. Owner: none now (a Stripe test key is needed in Phase 16).
- [x] **T0.4** API skeleton — 2026-11-01. `api/` on Python 3.12 with a `uv` lockfile: app factory, pydantic-settings (every secret a `SecretStr`; staging/production fail closed naming missing variables), structlog JSON logging with the plan's key-redaction list plus URL-password masking, request-id middleware, the `{error:{code,message,field?,request_id}}` envelope, `/api/v1/health` and `/ready`, gunicorn config, multi-stage Dockerfile (digest-pinned bases). Verified: 93 tests pass (3 integration tests against the live compose stack); `ruff` clean; `mypy --strict` clean on 25 files; no known vulnerabilities in the 47 locked packages. With redaction and URL-scrubbing disabled, 24 tests fail, so the tests do guard them. Container run hardened (read-only filesystem, all capabilities dropped): runs as uid 10001, `/ready` reports database and Redis ok, Docker health is healthy, 15 of 15 log lines are JSON with no secret or query string, stops cleanly in 0.6 s, and `APP_ENV=production` without settings exits 3 listing variable names only. Owner: none.
- [x] **T0.5** Database layer — 2026-11-01. `app/db/`: async engine; Alembic (async, refuses to run as anyone but `app_owner`) with migration `0001_foundations` (extensions, `uuid_generate_v7()`, `app_current_company_id()`, `set_updated_at()`); `app_owner`/`app_user` provisioning (idempotent, `python -m app.cli provision-db`); UUID v7 (Python and SQL); declarative base with `RecordMixin`/`TenantMixin`; RLS helpers; `TenantSession` (sets the company at the start of every transaction, scopes ORM queries, stamps and guards writes) and `GlobalSession`; FastAPI dependencies; `check-rls` drift guard. Verified: 162 tests pass (ruff and `mypy --strict` clean). **Done-when proof:** with raw SQL as `app_user`, company A cannot select, update, delete, insert or move company B's rows, and with no company set sees nothing. Also proved independently: the ORM filter works even on the owner connection (no RLS), the company survives a mid-request `commit()`, pooled connections do not leak it, and 12 concurrent sessions stay isolated. Five deliberate sabotages of the production code each turned the suite red. The provision, migrate and check path was run from the hardened container (read-only filesystem, no capabilities). **Found a real hole:** a plain view leaked every company's rows to `app_user`; fixed with a `security_invoker` helper and guards (see decision 16). Owner: none.
- [x] **T0.6** Web skeleton — 2026-11-01. `web/`: Next.js 16.4.2, React 19.3, TypeScript 5.9 strict, Tailwind v4, shadcn/ui (Radix, Lucide) initialised, ESLint 9, Prettier; route groups `(marketing) (auth) (app) (admin)` with minimal pages; `proxy.ts` with host routing, per-request nonce CSP and the section 4.6 headers; `/healthz`; standalone Dockerfile (non-root, digest-pinned). Verified: 87 unit tests and 23 Playwright tests pass, also when run against the hardened container (uid 10001, no capabilities, read-only filesystem); `tsc`, ESLint, `pnpm build` (env check, build, bundle secret scan) clean; `pnpm audit --prod` clean. Header checks cover every page, the nonce on every script tag, static assets and attacker-supplied headers. The `(admin)` pages are a 404 on the main host, including 20 encoded or odd path variants. Four deliberate breakages (unsafe-inline, no admin guard, no CSP header, reused nonce) each fail the suites. Found and fixed: a rewrite bug that made the admin host return 404 (decision 22). Owner: none.
- [x] **T0.7** Typed API client pipeline — 2026-11-01. `python -m app.cli export-openapi` (needs no environment, leaks nothing); `pnpm gen:api` / `gen:api:check` produce and verify `web/lib/api/schema.ts`; `web/lib/api/client.ts` (`openapi-fetch`, credentials included, CSRF header on writes, base-URL helpers); pre-commit hook for staleness. Verified: 172 API tests, 113 web unit tests (including compile-time type assertions), and 27 Playwright tests, among them a REAL call from the typed client to a running FastAPI server for `/health` and `/ready`. Fixed on the way: the spec advertised FastAPI's `HTTPValidationError` for 422 although the API returns the error envelope, so every operation now documents `ErrorEnvelope` for 4XX/5XX; and paths are now relative to a `/api/v1` server, so the client does not request `/api/v1/api/v1/health`. Owner: none.
- [x] **T0.8** CI pipelines — 2026-11-01. `.github/workflows/ci.yml` (10 jobs plus the **CI passed** gate), `security.yml` (weekly and manual ZAP baseline, staging only), `dependabot.yml` (weekly, grouped, 14-day cooldown), `.zap/rules.tsv`. **Verified:** CI run 41323265569 on `main` is green (all 11 jobs); Dependabot's first two pull requests (#1, #2) also ran the whole workflow on the `pull_request` trigger and passed. A fresh clone of the commit passes the API (172 tests), the web unit tests (113) and guard-script tests (32), the generated-types check, the build with bundle scan, and 29 Playwright tests. Every scanner was run locally first, which found and fixed real issues (decisions 26 to 29). **Fake-secret check:** the exact CI gitleaks command exits 0 on the clean history (9 commits) and 1 on a commit that adds a made-up secret, with the value redacted. **Not done:** the same check as a real GitHub pull request. Creating a branch and PR was blocked by the permission classifier and I did not work around it. If you want it, say so: I would open a draft PR, confirm it goes red, then close it and delete the branch. Owner: protect `main` (require **CI passed**); decide on Dependabot PRs #1 and #2 (see the table above).
- [x] **Phase 0 gate** — 2026-11-01. Full suite green on `b4be559` in CI; summary under *Phase summaries*. Owner: none blocking.

### Phase 1 — Design system and app shell
- [x] **T1.1** Tokens and theming — 2026-11-01. `web/app/globals.css`: the plan's colour tokens for light and dark (three ways to choose a theme, one result), the app and marketing type scales, radius, elevation, materials with solid fallbacks, page widths, hit targets and motion; `lib/motion.ts` presets with reduced-motion forms; the `theme` cookie with `ThemeSwitch`; Inter self-hosted through `next/font`; a brand-accent guard; and the development-only `/design` page. The unused shadcn-generated `Button` was removed (T1.2 builds the real one). **Verified:** 334 unit tests (every token against the plan, both themes against each other, 49 contrast pairs per theme at WCAG AA, type scale, motion, theme cookie, brand guard) and 61 Playwright tests, 26 of them in a real Chromium: every token's computed colour in both themes, contrast ratios as the browser resolves them, computed type sizes at three widths, theme switching with system/explicit/tampered cookies, reduced motion, and no horizontal scroll from 360 to 1920 px. Seven deliberate breakages of the stylesheet each turned the suites red. A custom brand accent was checked in a browser under the strict CSP. The production build does not contain `/design`; the image passes Trivy and runs hardened. CI now installs Chromium. **Found and fixed:** the plan's own colours fail its AA rule in a few places (decision 30), and a first version of the dev-only page leaked its title in the production 404 (decision 32). Owner: none.
- [x] **T1.2** Primitive components — 2026-11-01. 39 component files in `web/components/ui/` (more than 40 components; the list is in the README), each shown in every state on `/design`; the date and number logic, CSV export and table sorting are pure, separately tested modules in `lib/ui/`. **Verified:** 571 unit tests (including jsdom component tests for the combobox's stale-search ordering and debounce, table sorting, selection and keys, the typed-name deletion gate and calendar navigation) and 131 Playwright tests, 100 of them in Chromium: real keyboard behaviour (focus kept, trapped and returned) for **Dialog, Sheet, Menu, Combobox, SegmentedControl, DatePicker and DataTable**, plus the other controls; and **axe-core with zero violations** at WCAG 2.2 AA plus best practice, in light and dark, at desktop and phone width, with reduced motion, and with each of 11 overlays open. Seven deliberate breakages of the components and logic each failed a test. `pnpm audit` and Semgrep are clean. **Found and fixed on the way:** `tailwind-merge` dropped the text colour from every `text-<size> text-<colour>` pair, which turned filled buttons' labels black (decision 38); the invisible switch thumb (palette is off); a hydration mismatch for users with reduced motion; popovers announced as unnamed dialogs; and a calendar and table that overflowed a 360 px phone (decisions 37 to 42). **Deferred on purpose, to the tasks that own them:** CommandPalette and KeyboardShortcutsSheet (T1.4), AskMadyPanel (T14.4), OrgChart canvas (T12.2), WeekGrid (T9.5) and Charts (first use, T14.1). Owner: none.
- [x] **T1.3** App shell — 2026-11-01. `AppShell` for the signed-in app: translucent sidebar with the six groups and 21 pages, company switcher at the top and person at the bottom, collapse to 72 px with `[` (remembered by cookie, drawn by the server), a 56 px translucent toolbar (breadcrumbs, title, search, help, notifications bell, account menu with the theme), a phone tab bar with a "More" sheet, a skip link, the "Loading your workspace…" splash, and an empty page for every sidebar route. **Verified:** 612 unit tests (navigation, sidebar state, and component tests for the shell) and 198 Playwright tests. The shell runs against the production build at 390, 768, 1280 and 1920 px in light and dark: no sideways scroll, a 56 px toolbar, sidebar from 768 px and tab bar below it, content never under either, **axe zero violations in all eight combinations**, the open notification and account menus too, 44 px tab targets, the sheet's focus handling, and all 21 routes serving their page. Six deliberate breakages each failed a test. Semgrep clean. **Design QA (plan 5.12):** light and dark at 390, 768, 1280 and 1920 px, plus collapsed and the phone sheet, in `docs/screenshots/phase-1/`; 4 px spacing; one left edge; loading placeholders match the final layout (and stay round when collapsed); keyboard order (skip link first), visible focus and Esc closing the top layer checked in tests; axe clean; copy per 5.8; motion eases and is instant under reduced motion. **Found and fixed:** at 768 px the toolbar did not fit beside the sidebar and the page scrolled sideways by 52 px (the wide search box now starts at 1024 px; below that it is the icon). **Wired in later tasks:** search and help announce events that T1.4 listens for; Sign out arrives with T2.4/T3.4; counts and notifications with their APIs. Owner: none.
- [x] **T1.4** Command palette and shortcuts — 2026-11-02. `Ctrl/Cmd+K` palette (static pages, recents), `?` shortcuts sheet, one global handler (`[`, `G` then D/E/R/C/L/A/T, `/`, `N`, row keys and `.` row menu), all listed in the sheet. **Verified:** 6 Playwright checks (each shortcut, sheet lists all, axe 0 in light and dark with both overlays open) plus unit tests; axe found and I fixed a low-contrast palette hint, an unreachable scroll area and bad heading ids. Owner: none.
- [x] **T1.5** Marketing layout — 2026-11-02. Sticky translucent header with a phone menu sheet, 4-column footer with legal line from `brand.config.ts`, section components (hero, feature grid, alternating band, CTA band, FAQ accordion, pricing cards, headcount slider), cookie banner and preferences (`brand.cookieConsent`, Reject as easy as Accept), and a sample home page. **Verified:** Lighthouse mobile 95 / 100 / 96 / 100 (performance, accessibility, best practice, SEO); axe 0 on the home page at 4 widths × 2 themes, the menu and cookie dialog. Axe found and I fixed a low-contrast CTA lead. Header and footer links point at pages built in T18 and do not prefetch until then (decision 49). Owner: none.
- [x] **Phase 1 gate** — 2026-11-02, summary above.

### Phase 2 — Backend core (identity, tenancy, RBAC, audit, files, email)
- [x] **T2.1** Models — 2026-11-02. Migration `0002_identity_core`: companies, users, memberships, platform_admins, sessions, invitations, email_tokens, terms_versions and terms_acceptances, audit_events (append-only trigger plus no UPDATE/DELETE grant), files, notifications; `docs/data-model.md` is generated from the models and a test keeps it current. **Verified:** applies, rolls back to 0001 and to base, and re-applies cleanly; raw-SQL tests show companies cannot see each other's memberships or files, the audit trail cannot be updated, deleted or truncated even by the owner, and emails are unique whatever their case. Owner: none.
- [x] **T2.2** Crypto — 2026-11-02. `app/core/crypto.py` (AES-256-GCM, `v1:<kid>:` prefix, context bound as authenticated data, blind-index HMAC scoped by purpose and company, `mask_tail`), `EncryptedString` column type (`users.mfa_secret` now uses it), `python -m app.cli rotate-keys` (finds columns by type, repeatable), key settings validated at start in staging and production, runbook `docs/runbooks/key-rotation.md`. **Verified:** 27 tests: round trip, tamper and wrong-column refusal, rotation of stored rows to a new key and removal of the old one, bad key settings refused by name. Owner: none (generate the keys per deployment-requirements section 3 at T23).
- [x] **T2.3** Sessions and auth service — 2026-11-02. `app/modules/auth/`: argon2id (64 MB, 3, 4) with rule checks (12+ characters, NCSC common list, Have I Been Pwned range with a 2 s timeout), opaque 256-bit session tokens stored as hashes in Redis and Postgres (8 h idle, 14 days absolute, rotated on sign-in, second step and company switch), step-up for 10 minutes, TOTP written to RFC 6238 plus 10 hashed single-use recovery codes, per-IP and per-account rate limits, progressive lockout that treats unknown addresses exactly like real ones, a new-device alert hook, 72-hour single-use invitations; CSRF double-submit middleware and CORS for our two origins only. **Verified:** 50 new tests (lockout, rotation and expiry, CSRF refusal, MFA by policy, step-up, invitation expiry, RFC 6238 values) on a real Postgres and Redis. Owner: none. The e-mail for lockout and new-device alerts is sent by T2.8 (the `AuthNotifier` hook is in place).
- [x] **T2.4** Auth endpoints — 2026-11-02. All 19 `/auth` operations in plan section 11 (signup, verify, resend, login, logout, me, forgot/reset/change password, MFA setup/verify/challenge/disable/recovery codes, step-up, accept terms, invitations, switch company) with typed request and response models, the session cookie (HttpOnly, SameSite=Lax, parent domain when deployed), Turnstile after 3 failures and on public forms, a first terms version seeded by migration 0003, and the TypeScript client regenerated. **Verified:** 15 endpoint tests: the full sign-up to signed-in flow, identical answers for known and unknown addresses (sign-up, sign-in, forgot password), a reset ends every session, MFA challenge blocks until passed, step-up before turning it off, policy can forbid turning it off, invitation use-once and expiry, new terms, company switch (a stranger's company is a 404), and every operation documented. E-mails go through the `Mailer` interface; the sender is T2.8, so until then nothing is delivered. Owner: none.
- [x] **T2.5** RBAC — 2026-11-02. `app/core/rbac_matrix.py` holds the plan's 109 permissions plus the 11 new ones (the plan's count of 109 checks out) and all six roles, with HR Admin and Read-only Auditor built from the plan's rules and the others from its explicit lists; `require("permission")` checks the session, second step, verified e-mail, current terms, active membership and role in one place, opens the company-scoped database session, and says how far the permission reaches (all, reports, own); `ReportsGraph` finds direct and indirect reports for both the Reporting Authority and Leave Sanctioning chains with one recursive query, remembered for the request; the 7.3 rules (last Company Admin, who may invite or change roles, no self-approval) are functions with tests; `GET /auth/me` now returns `permissions`. **Verified:** 51 new tests: the matrix against the plan's own wording, all six roles against 25 permissions of every kind in a running app, each standing check, the reports query (depth, both chains, loops, other company), and a guard that fails if any endpoint is added without `require()` (so the RBAC matrix grows with each module). Owner: none.
- [x] **T2.6** Audit service — 2026-11-02. `record(db, context, action, ...)` adds the event to the caller's own transaction and masks sensitive fields (by name list and by patterns such as `*secret*`, `*token*`, `*_hash`), decimals as text; `access.audit(...)` in every `require()` endpoint fills in who, where from and the request id; `GET /audit-events` (filters, cursor paging, company-scoped, `compliance.audit.read`) and `GET /audit-events.csv` (`compliance.audit.export`, spreadsheet-formula safe, and itself audited); the auth endpoints now record company created, invitation accepted, password changed and two-step verification on/off. **Verified:** 24 new tests: a change and its event commit or vanish together (also when the event is the part that fails), raw NI numbers never reach the table, the ORM cannot edit or delete an event, listing, paging, filters and company scoping, role access (HR Admins read but cannot export), and the CSV. Owner: none.
- [ ] **T2.7** Files
- [ ] **T2.8** Email
- [ ] **T2.9** Worker and scheduler
- [ ] **Phase 2 gate**

### Phase 3 — Auth UI and onboarding
- [ ] **T3.1** Auth screens: login, MFA, forgot/reset password, verify email, accept invite
- [ ] **T3.2** Setup wizard, "Check your inbox" screen and Turnstile
- [ ] **T3.3** Terms gate, MFA enrolment flow and MFA policy enforcement
- [ ] **T3.4** Signed-in session bootstrap, permission-aware sidebar, free-plan banner, 402 upgrade sheet
- [ ] **Phase 3 gate** — includes the Playwright E2E journey in plan Phase 3

### Phase 4 — Company settings
- [ ] **T4.1** Company overview, Details, Companies House lookup, logo upload
- [ ] **T4.2** Locations, departments, designations
- [ ] **T4.3** Key personnel
- [ ] **T4.4** Compliance documents
- [ ] **T4.5** Working pattern, bank-holiday import job, holiday types, company holidays
- [ ] **T4.6** Trading hours
- [ ] **T4.7** Bank accounts, tax codes, payment types, pay bands, pay schedules
- [ ] **Phase 4 gate** — inset-grouped style, RBAC tests and audit events for every change

### Phase 5 — Users and access
- [ ] **T5.1** User Access list, filters, unlinked-users banner
- [ ] **T5.2** Invite flow, role change, suspend/reactivate, reset 2FA, link/unlink employee
- [ ] **T5.3** MFA policy setting and "What can each role do?" viewer
- [ ] **Phase 5 gate**

### Phase 6 — Employees
- [ ] **T6.1** Employee model, list page, archived list
- [ ] **T6.2** Create page and unique-number rule
- [ ] **T6.3** Profile header, Overview tab, lifecycle status, 48 h opt-out, guarded permanent delete
- [ ] **T6.4** Personal tab
- [ ] **T6.5** Employment tab
- [ ] **T6.6** Salary
- [ ] **T6.7** Documents tab and employee record PDF
- [ ] **T6.8** Leave, Attendance, Learning and Activity tab shells
- [ ] **Phase 6 gate** — no inline auto-save; RBAC and isolation tests for every endpoint

### Phase 7 — Right to Work and sponsor compliance
- [ ] **T7.1** Right to Work checks
- [ ] **T7.2** Sponsor documents and sponsored employees page
- [ ] **T7.3** Working-day calculator, change of circumstances, org changes
- [ ] **T7.4** Reminders engine and register page
- [ ] **T7.5** Compliance hub
- [ ] **T7.6** Employee Sponsor Compliance tab, sponsor record PDF, "Needs attention" feed
- [ ] **Phase 7 gate** — scenario tests from plan Phase 7

### Phase 8 — Leave and holidays
- [ ] **T8.1** Leave types and leave settings
- [ ] **T8.2** Ledger and balance computation
- [ ] **T8.3** Requests, conflicts, approvals, attendance sync
- [ ] **T8.4** `/leave` screens, My Leave, My Approvals, profile Leave tab
- [ ] **T8.5** Year-end carry-over
- [ ] **Phase 8 gate**

### Phase 9 — Attendance, Rota, Work Log
- [ ] **T9.1** Attendance records and workspace
- [ ] **T9.2** Import, bulk grid, exports, absences report
- [ ] **T9.3** Clock in/out and timesheet approval
- [ ] **T9.4** Shift types, late policies, day-off patterns
- [ ] **T9.5** Rota week grid, publish, print, My Shifts
- [ ] **T9.6** Work Log
- [ ] **Phase 9 gate**

### Phase 10 — Documents, policies and reports
- [ ] **T10.1** Company documents
- [ ] **T10.2** Reports
- [ ] **T10.3** Policies and sign-offs
- [ ] **T10.4** "Draft with AI" UI and API contract (feature-flagged)
- [ ] **Phase 10 gate**

### Phase 11 — Recruitment and public careers
- [ ] **T11.1** Requisitions
- [ ] **T11.2** Postings
- [ ] **T11.3** Candidates
- [ ] **T11.4** Applications, interviews, offers
- [ ] **T11.5** Convert to employee
- [ ] **T11.6** Public careers pages and apply form
- [ ] **Phase 11 gate**

### Phase 12 — Org chart
- [ ] **T12.1** Tree API and hierarchy levels
- [ ] **T12.2** Canvas, list view, unassigned section, PDF export
- [ ] **Phase 12 gate**

### Phase 13 — Learning
- [ ] **T13.1** Course model, minimal editor, course player
- [ ] **T13.2** Write the 8 original courses
- [ ] **T13.3** Assign wizard, report view and export, overdue job, My Learning
- [ ] **T13.4** Certificates and public `/verify`
- [ ] **Phase 13 gate**

### Phase 14 — Dashboard, notifications, search, and the AI assistant
- [ ] **T14.1** Dashboard API, cards and setup checklist
- [ ] **T14.2** Notifications
- [ ] **T14.3** Command palette live search
- [ ] **T14.4** Anthropic integration, redaction layer, tools, assistant panel
- [ ] **T14.5** Wire AI into letter drafting and reminder wording
- [ ] **Phase 14 gate** — AI payload fuzz test

### Phase 15 — Sponsorship Job Checker (SOC)
- [ ] **T15.1** ONS SOC data import and local embeddings
- [ ] **T15.2** Rules-data importer (draft rules version, fixtures, salary rules)
- [ ] **T15.3** Rules engine and 20+ golden tests
- [ ] **T15.4** Search and match API
- [ ] **T15.5** CV match
- [ ] **T15.6** Checker UI, "Find code" embeds, PDF report
- [ ] **T15.7** Daily rules watcher and super-admin diff/publish/rollback
- [ ] **T15.8** Public free version
- [ ] **Phase 15 gate**

### Phase 16 — Billing, plans and account lifecycle
- [ ] **T16.1** Stripe integration and webhooks
- [ ] **T16.2** Entitlements and payment-failed grace
- [ ] **T16.3** Billing page, cancel with refund
- [ ] **T16.4** Data export
- [ ] **T16.5** Delete account
- [ ] **Phase 16 gate** — Stripe test-mode E2E for both plans, refund, cancel, failed payment, webhook replay

### Phase 17 — Super-admin back office
- [ ] **T17.1** Platform admin auth and admin host routing
- [ ] **T17.2** Overview metrics, companies, users search
- [ ] **T17.3** Support mode (impersonation)
- [ ] **T17.4** Subscriptions and refunds, deletion and export queue, contact inbox
- [ ] **T17.5** Content tools and feature flags
- [ ] **T17.6** Jobs dashboard, register status, rules data screens, platform audit log
- [ ] **Phase 17 gate**

### Phase 18 — Public marketing site
- [ ] **T18.1** Home, Features, Pricing, Security, About, Contact, Accessibility, Careers, Sponsor compliance
- [ ] **T18.2** Legal pages (DRAFT, requires solicitor review)
- [ ] **T18.3** SEO and Lighthouse ≥ 95
- [ ] **T18.4** Comparison page templates (unpublished)
- [ ] **Phase 18 gate**

### Phase 19 — Free tools, guides and templates
- [ ] **T19.1** Rates data files, verified from GOV.UK and HMRC
- [ ] **T19.2** Calculator 1: right-to-work-october-2026-checker
- [ ] **T19.3** Calculator 2: sponsor-licence-cost-calculator
- [ ] **T19.4** Calculator 3: sponsor-reporting-deadline-calculator
- [ ] **T19.5** Calculator 4: skilled-worker-visa-checker
- [ ] **T19.6** Calculator 5: ilr-citizenship-checker
- [ ] **T19.7** Calculator 6: skilled-worker-ilr-salary-calculator
- [ ] **T19.8** Calculator 7: holiday-entitlement-calculator
- [ ] **T19.9** Calculator 8: uk-take-home-salary-calculator
- [ ] **T19.10** Calculator 9: uk-employer-cost-calculator
- [ ] **T19.11** Calculator 10: uk-redundancy-pay-calculator
- [ ] **T19.12** Calculator 11: uk-notice-pay-calculator
- [ ] **T19.13** Calculator 12: uk-sick-pay-calculator
- [ ] **T19.14** Calculator 13: uk-minimum-wage-underpayment-checker
- [ ] **T19.15** Tool 14: risk-assessment-template
- [ ] **T19.16** Guides, including the 26-question audit self-test
- [ ] **T19.17** Templates
- [ ] **T19.18** Resources hub pages
- [ ] **Phase 19 gate**

### Phase 20 — Public sponsor register
- [ ] **T20.1** Ingest pipeline
- [ ] **T20.2** Geocoding, ITL1 regions, SVG map, Companies House bulk match
- [ ] **T20.3** Explore page
- [ ] **T20.4** Region pages, change bulletins, profile pages, methodology, report form, sitemaps
- [ ] **Phase 20 gate**

### Phase 21 — Security hardening pass
- [ ] **T21.1** Full security test suite and RBAC matrix coverage of every endpoint
- [ ] **T21.2** Threat model (`docs/security.md`)
- [ ] **T21.3** Dependency, container and secret scans clean; CSP enforced
- [ ] **T21.4** Pen-test style checks
- [ ] **T21.5** Privacy review
- [ ] **Phase 21 gate**

### Phase 22 — Quality, performance, accessibility
- [ ] **T22.1** Full E2E suite for the top 25 journeys
- [ ] **T22.2** Performance budgets
- [ ] **T22.3** Accessibility audit
- [ ] **T22.4** Design QA sweep with final screenshots
- [ ] **Phase 22 gate**

### Phase 23 — Deployment (Railway + Cloudflare)
Needs the owner's accounts and variables (see "Owner actions needed").
- [ ] **T23.1** Railway project, environments and services
- [ ] **T23.2** Database roles, reference data seeding, first Platform Admin
- [ ] **T23.3** Cloudflare DNS, TLS, WAF, rate limit, Turnstile, R2 buckets
- [ ] **T23.4** Resend, Stripe, Sentry and uptime monitor set-up
- [ ] **T23.5** GitHub Actions deploy workflows
- [ ] **T23.6** Backups, restore test and runbooks
- [ ] **T23.7** Staging acceptance
- [ ] **T23.8** Production go-live
- [ ] **Phase 23 gate**

### Phase 24 — Launch checklist and handover
- [ ] **T24.1** Complete the launch checklist (plan section 12) and write `docs/handover.md`

### Phase 25 — Later
Do not start until the owner says so: US site, Australia, native wrapper, passkeys, calendar-synced SMS reminders.
