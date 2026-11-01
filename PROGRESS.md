# PROGRESS

Build log for the platform described in [`plan.md`](plan.md). Tasks are done strictly in
order. After every task: tick it, add one line saying what was done and anything the owner
must do, and commit. Never record secret values in this file.

- **Last updated:** 2026-11-01
- **Current task:** T0.6 Web skeleton

---

## Owner actions needed

### Blocking now

None.

### Coming up (not blocking yet)

Everything in Phases 0 to 22 runs locally. Nothing below needs doing until the phase shown,
unless a task notes otherwise here.

| Needed by | Owner action | Source |
|---|---|---|
| T0.8 | ~~Create the private GitHub repository~~ — done: `zohaib5911/hrcmr`, confirmed private. Still to do: turn on **Settings → Security → Private vulnerability reporting** (referenced by `SECURITY.md`), and later enable branch protection on `main` and the GitHub Actions secrets (section 6 of deployment-requirements). | plan T0.8, SECURITY.md |
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

---

## Environment notes

Checked 2026-11-01 on the build machine: git 2.56, Node 24.21, Python 3.14.8 (the plan needs **3.12**, which I will provision with `uv`), uv 0.12, Docker 29.9. `pnpm` is not installed; I will enable it via Corepack in T0.6.

---

## Phase summaries

Written at each phase gate, with screenshots in `docs/screenshots/<phase>/`.

---

## Task list

### Phase 0 — Foundations and guard-rails
- [x] **T0.1** Repo initialisation — 2026-11-01. `git init -b main`; full Section 3 directory tree; README, SECURITY, PROGRESS (all 145 task ids, checked against plan.md by script), `.gitignore`, `.editorconfig`, `brand.config.ts`, `docs/architecture.md`. Owner: none.
- [x] **T0.2** Secret guard-rails before any code — 2026-11-01. `.gitleaks.toml` (default ruleset + 7 project rules), `.pre-commit-config.yaml` (gitleaks, ruff, ruff-format, prettier, eslint, plus detect-private-key and the NEXT_PUBLIC allowlist), `.env.example` (53 names, values empty; a test keeps it identical to deployment-requirements §4), `scripts/check-public-env.mjs`, `scripts/scan-bundle.mjs`, 32 unit tests. Proved in a throwaway clone: a fake `sk_live_` key and 6 other leak types are blocked (output redacted), a clean commit passes, `git check-ignore .env` → ignored; gitleaks finds nothing in the tree or history. Owner: none.
- [x] **T0.3** Local stack (Docker Compose) — 2026-11-01. `docker-compose.yml`: postgres+pgvector 0.8.7/pg16, redis 7.4, RustFS 1.0.4 (+ one-shot `files-dev` bucket job), mailpit 1.33, clamav 1.5.4, stripe-cli under profile `stripe`; every port bound to 127.0.0.1; healthchecks and named volumes; README section. Verified by running it: `docker compose up -d --wait` exits 0 (about 11 s warm) with all services healthy; Postgres 16.15 creates pgcrypto, pg_trgm, unaccent, vector and citext and runs a pgvector query; Redis answers with AOF on; RustFS passed 14 S3 checks; Mailpit round-trips an SMTP message; ClamAV detects EICAR (plain, in 7-byte chunks, and inside a ZIP) and passes clean data; Postgres, Redis and bucket data survive `down`/`up`; the Stripe CLI exits with a clear message when no key is set. Owner: none now (a Stripe test key is needed in Phase 16).
- [x] **T0.4** API skeleton — 2026-11-01. `api/` on Python 3.12 with a `uv` lockfile: app factory, pydantic-settings (every secret a `SecretStr`; staging/production fail closed naming missing variables), structlog JSON logging with the plan's key-redaction list plus URL-password masking, request-id middleware, the `{error:{code,message,field?,request_id}}` envelope, `/api/v1/health` and `/ready`, gunicorn config, multi-stage Dockerfile (digest-pinned bases). Verified: 93 tests pass (3 integration tests against the live compose stack); `ruff` clean; `mypy --strict` clean on 25 files; no known vulnerabilities in the 47 locked packages. With redaction and URL-scrubbing disabled, 24 tests fail, so the tests do guard them. Container run hardened (read-only filesystem, all capabilities dropped): runs as uid 10001, `/ready` reports database and Redis ok, Docker health is healthy, 15 of 15 log lines are JSON with no secret or query string, stops cleanly in 0.6 s, and `APP_ENV=production` without settings exits 3 listing variable names only. Owner: none.
- [x] **T0.5** Database layer — 2026-11-01. `app/db/`: async engine; Alembic (async, refuses to run as anyone but `app_owner`) with migration `0001_foundations` (extensions, `uuid_generate_v7()`, `app_current_company_id()`, `set_updated_at()`); `app_owner`/`app_user` provisioning (idempotent, `python -m app.cli provision-db`); UUID v7 (Python and SQL); declarative base with `RecordMixin`/`TenantMixin`; RLS helpers; `TenantSession` (sets the company at the start of every transaction, scopes ORM queries, stamps and guards writes) and `GlobalSession`; FastAPI dependencies; `check-rls` drift guard. Verified: 162 tests pass (ruff and `mypy --strict` clean). **Done-when proof:** with raw SQL as `app_user`, company A cannot select, update, delete, insert or move company B's rows, and with no company set sees nothing. Also proved independently: the ORM filter works even on the owner connection (no RLS), the company survives a mid-request `commit()`, pooled connections do not leak it, and 12 concurrent sessions stay isolated. Five deliberate sabotages of the production code each turned the suite red. The provision, migrate and check path was run from the hardened container (read-only filesystem, no capabilities). **Found a real hole:** a plain view leaked every company's rows to `app_user`; fixed with a `security_invoker` helper and guards (see decision 16). Owner: none.
- [ ] **T0.6** Web skeleton
- [ ] **T0.7** Typed API client pipeline
- [ ] **T0.8** CI pipelines
- [ ] **Phase 0 gate** — full suite, summary here, nothing broken

### Phase 1 — Design system and app shell
- [ ] **T1.1** Tokens and theming
- [ ] **T1.2** Primitive components
- [ ] **T1.3** App shell
- [ ] **T1.4** Command palette and shortcuts
- [ ] **T1.5** Marketing layout
- [ ] **Phase 1 gate**

### Phase 2 — Backend core (identity, tenancy, RBAC, audit, files, email)
- [ ] **T2.1** Models
- [ ] **T2.2** Crypto
- [ ] **T2.3** Sessions and auth service
- [ ] **T2.4** Auth endpoints
- [ ] **T2.5** RBAC
- [ ] **T2.6** Audit service
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
