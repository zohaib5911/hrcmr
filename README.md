# Brand: UK HR and sponsor-compliance platform

A UK HR and **sponsor-licence compliance** web platform for small employers. It does not
run payroll; it works alongside the customer's payroll provider.

"Brand" is a placeholder name. The real name, logo and accent colour are set in
[`brand.config.ts`](brand.config.ts).

## Status

The project is built task by task from [`plan.md`](plan.md). Current progress, owner
actions and phase summaries are in [`PROGRESS.md`](PROGRESS.md). Everything the owner must
prepare (accounts, keys, domain, legal details) is in
[`deployment-requirements.txt`](deployment-requirements.txt).

## Repository layout

| Path | What it holds |
|---|---|
| `web/` | Next.js app: public website, company app, super-admin back office |
| `api/` | FastAPI backend, Alembic migrations, tests, dev-only seed data |
| `data/` | Reference-data sources and import scripts (ONS SOC index, rules tables) |
| `docs/` | Architecture, security, runbooks, screenshots |
| `.github/workflows/` | CI, security scans, deploy pipelines |
| `brand.config.ts` | Brand name, tagline, logo paths, accent colour |

The architecture is summarised in [`docs/architecture.md`](docs/architecture.md).

## Working agreement

- Work is done one task at a time, in the order of `plan.md` section 9, and every task is
  committed with a Conventional Commit message that ends with its task id, for example
  `feat(leave): add balances ledger (T8.2)`.
- A task is done only when its checks pass: lint, type-check and tests.
- **Secrets never go into the repository, the chat or the logs.** See
  [`SECURITY.md`](SECURITY.md) for where secret values live and what to do if one is exposed.
- Rates, thresholds and immigration rules come only from official sources and are stored
  with their source URL and the date they were checked.

## Prerequisites

Docker Engine with the Compose v2 plugin, Node.js 24 and pnpm, Python 3.12 with `uv`, and git.
Commands for the tests and the deployment are added to this file by the tasks that create them
(API, web, CI and deployment).

## Local stack (Docker Compose)

Everything the app needs runs on your machine, so Phases 0 to 22 need no production accounts.

```bash
docker compose up -d --wait        # start everything; returns when all services are healthy
docker compose ps                  # status
docker compose logs -f clamav      # watch a service (first ClamAV start downloads signatures)
docker compose down                # stop, keep data
docker compose down -v             # stop and delete ALL local data
```

Docker must be running first. On Arch Linux: `sudo systemctl enable --now docker.service`, and your
user must be in the `docker` group (log out and in again after adding it).

| Service | Address (this machine only) | Stands in for | Notes |
|---|---|---|---|
| `postgres` | `localhost:5432`, database `app` | Railway Postgres | PostgreSQL 16 with pgvector. User `postgres`; roles `app_owner` and `app_user` are created by T0.5. |
| `postgres-test` | `localhost:5433` | none | Disposable Postgres (in memory) used by the automated tests. Resets on restart. |
| `redis` | `localhost:6379` | Railway Redis | Sessions, rate limits, job queue. |
| `rustfs` | S3 API `http://localhost:9000`, console `http://localhost:9001` | Cloudflare R2 | Private bucket `files-dev` is created by the one-shot `rustfs-init` job, which then exits (that is normal). |
| `mailpit` | SMTP `localhost:1025`, inbox `http://localhost:8025` | Resend | Catches every e-mail. Nothing leaves your machine. |
| `clamav` | `localhost:3310` | ClamAV on Railway | First start downloads about 300 MB of signatures and takes several minutes; needs about 1.5 GB RAM. Signatures are kept in a volume, so later starts are quick. |
| `stripe-cli` | none | Stripe webhooks | Off by default; see below. |

All ports are bound to `127.0.0.1`. The local credentials (`postgres`/`postgres` for Postgres,
`rustfsadmin` for RustFS) protect throwaway containers only. Override any of them, or any port
(`POSTGRES_PORT`, `POSTGRES_TEST_PORT`, `REDIS_PORT`, `S3_PORT`, `S3_CONSOLE_PORT`, `MAILPIT_SMTP_PORT`,
`MAILPIT_UI_PORT`, `CLAMAV_PORT`), in a local `.env`. If you change `RUSTFS_ACCESS_KEY` or
`RUSTFS_SECRET_KEY`, set `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY` to the same values.

**Stripe webhooks (from Phase 16).** Put a Stripe **test-mode** key in your own `.env` as
`STRIPE_SECRET_KEY`, run `docker compose --profile stripe up -d stripe-cli`, then read the webhook
signing secret from `docker compose logs stripe-cli` and put it in `.env` as
`STRIPE_WEBHOOK_SECRET`. Do not paste either value into chat.

**Why RustFS and not MinIO?** The plan named MinIO as the local stand-in for R2. Its community
project has been archived and its Docker images withdrawn, so RustFS (Apache-2.0, S3-compatible)
was chosen with the owner's approval. Production still uses Cloudflare R2.

## API (`api/`, FastAPI on Python 3.12)

```bash
cd api
uv sync                                   # installs exactly what uv.lock says (fetches Python 3.12 if needed)
uv run ruff check . && uv run ruff format --check . && uv run mypy      # lint, format, mypy --strict
docker compose up -d --wait               # from the repo root: the integration tests need Postgres and Redis
uv run pytest                             # fails with a clear message if the stack is not running
uv run uvicorn app.main:create_app --factory --reload --port 8000       # needs a .env, see below
uv run python -m app.jobs.worker          # the background worker: sends queued e-mail, runs the schedule
docker build -t brand-api:dev api/        # production image: multi-stage, non-root (uid 10001), pinned digests
```

- **Endpoints:** `GET /api/v1/health` (liveness) and `GET /api/v1/ready` (Postgres and Redis; `503` if either is down). Interactive docs at `/api/v1/docs` when `APP_ENV` is `local` or `test`; they are not served when deployed.
- **E-mail and background jobs:** the API saves each e-mail in an outbox and the worker sends it, through Resend when `RESEND_API_KEY` is set and otherwise through Mailpit (add `SMTP_HOST=localhost` to your `.env`; it is not in `.env.example` because it is for development only; inbox at http://localhost:8025). Start the worker next to the API; `python -m app.cli email-samples` (development only; the code is in `api/seed/` and is not in the production image) sends one of every template to Mailpit. The schedule (UTC) is in `api/app/jobs/scheduled.py`; each run is logged and recorded in the audit trail.
- **Errors** always look like `{"error": {"code", "message", "field"?, "request_id"}}`, and every response carries `X-Request-ID`.
- **Configuration** comes from environment variables, and locally from the git-ignored `.env` in the repo root (`app/core/config.py`). Always required: `APP_ENV` (`local`, `test`, `staging` or `production`), `DOMAIN`, `WEB_ORIGIN`, `ADMIN_ORIGIN`, `API_ORIGIN`, `DATABASE_URL`, `REDIS_URL`, `SESSION_SECRET`, `FIELD_ENCRYPTION_KEYS`, `BLIND_INDEX_KEY`. `staging` and `production` refuse to start unless every third-party setting is present, and the error names the missing variables, never their values. Generate secrets with the commands in `deployment-requirements.txt` section 3.
- **Logs** are one JSON object per line. Keys such as `password`, `token`, `authorization`, `ni_number` and `salary` are dropped, and passwords inside URLs are masked. Access lines never include the query string.

## Web (`web/`, Next.js 16 with TypeScript, Tailwind v4, shadcn/ui)

```bash
corepack enable --install-directory ~/.local/bin pnpm   # one-off; pnpm's version comes from web/package.json
cd web
pnpm install
pnpm dev                       # http://localhost:3000 (public site/app) and http://admin.localhost:3000 (back office)
pnpm lint && pnpm typecheck && pnpm test      # ESLint, tsc --strict, Vitest
pnpm exec playwright install chromium   # one-off: the browser the design-page tests use
pnpm test:e2e                  # production build (headers, host routing, typed client) and the /design page in Chromium
docker build -f web/Dockerfile -t brand-web:dev .    # run from the REPO ROOT (brand.config.ts and scripts/ live there)
```

- **Hosts.** `proxy.ts` (called `middleware.ts` before Next.js 16) routes by `Host`. `admin.*` serves the back office, which lives under an internal `/platform` segment that is a 404 on every host when requested directly. The admin host serves nothing else. Cloudflare must not rewrite the `Host` header.
- **Security headers.** A per-request nonce Content-Security-Policy, HSTS, `nosniff`, `X-Frame-Options: DENY`, a strict referrer policy and a Permissions-Policy (`lib/security/csp.ts`). Because the nonce changes per request, pages are rendered per request.
- **Secrets.** Only the nine allow-listed `NEXT_PUBLIC_*` names reach the browser, and `pnpm build` runs `scripts/check-public-env.mjs` first and `scripts/scan-bundle.mjs` after. The web service holds no third-party keys.
- **Container.** Next.js decides whether a rewrite is internal by comparing origins with the address the server is bound to. Bind `0.0.0.0` (the image sets `HOSTNAME=0.0.0.0`; a platform that overrides `HOSTNAME` must set it back). Bound to `127.0.0.1` the admin rewrite fails with a 500, never exposing admin pages.
- **Dependencies.** `web/pnpm-workspace.yaml` refuses any package version published less than 14 days ago and blocks install scripts.

### Design system (`web/app/globals.css`)

The tokens from plan section 5 live in one stylesheet, and tests hold it to the plan.

- **Colours** are CSS variables (`--bg`, `--label`, `--accent`, `--success`, ...) with light and dark values. Use the Tailwind names that point at them (`bg-canvas`, `bg-elevated`, `text-label`, `text-label-secondary`, `bg-accent text-on-accent`, `text-accent-text` for links, `bg-success-tint text-success` for a chip). Tailwind's default palette is switched off, so `bg-blue-500` does not exist; a component can only use a token.
- **Type scale** (`text-large-title`, `text-title-1` to `text-title-3`, `text-headline`, `text-body`, `text-callout`, `text-subheadline`, `text-footnote`, `text-caption`; marketing `text-hero`, `text-section`, `text-lead`), **radius** (`rounded-control`, `-popover`, `-card`, `-sheet`, `-pill`), **elevation** (`shadow-e1` to `shadow-e3`; hairline borders in dark), **materials** (`material-chrome`, `material-sheet`), **page width** (`page-app`, `page-marketing`), **touch targets** (`hit-target`) and **motion** (`motion-micro`, `motion-small`, `motion-sheet`; the spring and variants are in `lib/motion.ts`).
- **Theme.** The user's choice is a `theme` cookie (`light` or `dark`; none means follow the system), which the server stamps on `<html data-theme>` before the first byte, so there is no flash and no inline script. Any element can carry `data-theme` to preview the other theme inside a page. `components/app/theme-switch.tsx` changes it.
- **`/design`** (`http://localhost:3000/design`) shows every token in both themes side by side, with the type scale, spacing and motion. It exists **only in development**: the file is `page.dev.tsx`, and `next.config.ts` enables that page extension outside production, so a production build does not contain the route at all.
- **Brand colour.** `brand.config.ts` may change the accent colour and nothing else. `lib/design/brand-style.ts` refuses any colour that would make button labels or links fail WCAG AA.
- **Fonts.** Inter, from the `@fontsource-variable/inter` package, is served from this site (no request to Google). The system font is first in the stack, so Apple devices show their own.

### Components (`web/components/ui/`)

Every primitive from plan section 5.7 that is not owned by a later task: buttons, text and number
fields, search, text area, select, combobox, date and date-range pickers, time picker, file drop,
switch, checkbox, radio cards, segmented control, tabs, card, dialog, sheet, confirm dialog, inline
confirm, popover, menus, tooltip, toasts, alert, empty and error states, skeletons, progress, stepper,
chips, avatars, KPI card, timeline, calendar and the data table. Run `pnpm dev` and open
`http://localhost:3000/design` to see each one in all its states, in both themes.

Rules that the tooling enforces:

- **Tokens only.** Tailwind's default palette is off, so use `bg-elevated`, `text-label`, `bg-accent-tint`, not `bg-white`. A test fails on any raw colour class.
- **No `style=""`.** The Content-Security-Policy blocks inline styles in server-rendered HTML, so they silently do nothing in production. ESLint rejects the `style` prop; use classes or SVG attributes.
- **Join classes with `cn()`** from `lib/utils`. It knows this design system's text sizes, radii and shadows. Plain `tailwind-merge` does not, and drops the colour from `text-callout text-on-accent`.
- **Contrast.** On the grey input fill, use `text-label` or `text-placeholder`, never `text-label-secondary` (4.1 to 4.4:1). `text-label-tertiary` is for large text and icons only. Use a gray or filled button inside a coloured alert, not a tinted one. `pnpm test` and the axe suite check all of this.
- **Dates are ISO strings** (`"2026-11-01"`), never `Date` objects. The pickers show `1 Nov 2026` and read `1/11/26`, day first.
- **Providers.** `TooltipProvider` and `ToastProvider` go once near the root (the app shell does this from T1.3).

Tests: logic in `lib/ui/*.test.ts` and `components/ui/*.test.tsx` (`pnpm test`, jsdom); real-browser keyboard,
focus and layout in `tests/e2e/design-components.spec.ts`; accessibility in `tests/e2e/design-a11y.spec.ts`
(axe-core, zero violations, both themes, phone width, reduced motion, and every overlay while it is open).

### The signed-in app shell (`web/app/(app)/`, `web/components/app/`)

Every signed-in page is drawn inside `AppShell`: a translucent 260 px sidebar (72 px collapsed; press
`[`, and the choice is remembered in a cookie so the server draws it right), a sticky 56 px toolbar with
breadcrumbs, the page title, search, help, notifications and the account menu, and on phones a bottom
tab bar (Home, People, Compliance, Time, Me) with a "More" sheet.

- **One list.** `lib/navigation.ts` defines every sidebar item once; the sidebar, tab bar, breadcrumbs and placeholder pages are built from it, and a test fails if an item has no page. To add a page: add it there, create `app/(app)/<route>/page.tsx`.
- **Placeholder pages.** Each sidebar route has a page (`PlaceholderPage`) that says what will appear there. The feature task that owns a route replaces it with the real page, using `PageHeader` for the title.
- **No session yet.** Until the sign-in work (T3.4) the layout passes `session={null}` and the company and person show as loading placeholders, not invented names. Counts on sidebar rows come from the `badges` prop, and the bell's from `notificationCount`; both are empty until the API supplies them.
- **Evidence.** Design QA screenshots (four widths, both themes, collapsed, phone sheet) are in `docs/screenshots/phase-1/`. Regenerate them with `SCREENSHOTS=1 pnpm exec playwright test shell-screenshots --project=production`.

### Typed API client

The API is the contract. `pnpm gen:api` (run in `web/`, needs `uv`) exports the OpenAPI document with `python -m app.cli export-openapi` and writes `web/lib/api/schema.ts`; never edit that file. `pnpm gen:api:check` fails if it is stale (a pre-commit hook runs it when API code changes). Use the client from `web/lib/api/client.ts`: `createApiClient({ baseUrl })` is typed against the schema, sends the session cookie, and adds the CSRF header on state-changing requests. Paths in the spec are relative to the `/api/v1` server, so `NEXT_PUBLIC_API_URL` ends in `/api/v1`.

### Database (PostgreSQL 16, Row-Level Security)

Two login roles, both created by a one-off superuser step and neither able to bypass Row-Level
Security: **`app_owner`** owns the schema and runs migrations, and **`app_user`** is what the running
API connects as. Every tenant table is confined to one company by the database itself, and
`TenantSession` (`app/db/session.py`) adds a second, application-level filter.

```bash
# One-off per environment. Needs a SUPERUSER URL, passed only for this command (never in the API's settings):
DATABASE_URL_ADMIN=postgresql+asyncpg://postgres:...@host/db  uv run python -m app.cli provision-db
uv run python -m app.cli migrate          # alembic upgrade head, as app_owner (refuses any other role)
uv run python -m app.cli check-rls        # fails if a tenant table, view or function breaks the rules below
uv run alembic revision --autogenerate -m "describe the change"
```

`provision-db` takes the role names and passwords from `DATABASE_URL_OWNER` and `DATABASE_URL`
(user must be `app_owner` / `app_user`), so there is nothing extra to configure. It is safe to re-run.

**Rules for anyone writing a migration** (a test fails if they are broken):

- A table with a `company_id` column must call `enable_tenant_rls("table")` in `upgrade()`; a table with `updated_at` must call `add_updated_at_trigger("table")`. Use `RecordMixin` and `TenantMixin` from `app/db/base.py`.
- A view over tenant tables **must** be made with `create_tenant_view(...)`. A plain view runs as its owner, who is not subject to the policy, and shows every company's rows. Materialised views and `SECURITY DEFINER` functions are not allowed.
- Raw SQL (`text()`, `exec_driver_sql`) lives only under `app/db/`. Everything else goes through the ORM via `TenantSession`.

The tests use a **disposable Postgres** (`postgres-test`, port 5433, in memory), never your development database, because roles are cluster-wide and the tests create and re-password them.

## Secret guard-rails (set up once per clone)

```bash
uv tool install pre-commit     # one-off, user-level
pre-commit install             # installs the git hook for this clone
node --test 'scripts/tests/*.test.mjs'   # unit tests for the guard scripts
```

| Guard | What it stops |
|---|---|
| `gitleaks` hook (`.gitleaks.toml`) | Committing API keys, webhook secrets, private keys, or a known secret variable set to a literal value. Also run in CI over the full history. |
| `scripts/check-public-env.mjs` | Any `NEXT_PUBLIC_*` variable outside the 9 allowlisted names, or an allowlisted one holding a secret-shaped value. |
| `scripts/scan-bundle.mjs` | Secret prefixes, or the literal value of a secret environment variable, inside the built browser bundle (`web/.next/static`, `web/public`). Fails if the build is missing. |
| `.gitignore` | `.env`, `.env.*` (except `.env.example`), `*.pem`, `*.key`, `/secrets`. |

`.env.example` lists variable **names only**. Copy it to `.env` for local development and use
test keys only. Staging and production values are set in the Railway dashboard. The guard scripts
report the file, line and rule that matched, never the matched value.

## Continuous integration (GitHub Actions)

`.github/workflows/ci.yml` runs on every pull request to `main` and every push to `main`. Each job
is something you can also run on your machine.

| Job | What it checks | Run it locally |
|---|---|---|
| Secret scan | gitleaks over the **whole git history** (output redacted) | `pre-commit run gitleaks --all-files` (staged changes only) |
| Formatting and hygiene | prettier, ruff format, private keys, merge markers, `NEXT_PUBLIC_*` allowlist | `pre-commit run --all-files` |
| API | ruff, ruff format, `mypy --strict`, pytest against Postgres 16 and Redis | see **API** above |
| Web | ESLint, `tsc`, Vitest, guard-script tests, generated API types up to date, production build, `NEXT_PUBLIC_*` check, **browser-bundle secret scan** | see **Web** above |
| End-to-end | Playwright on the production build and a live API | `pnpm test:e2e` |
| Dependency audit | `pip-audit` on the locked Python packages; `pnpm audit` (production: moderate and above; dev tools: high and above) | `pnpm audit --prod` in `web/` |
| Static analysis | Semgrep (`p/default`, Python, TypeScript, Next.js, Dockerfile, Actions, OWASP Top 10) | `docker run --rm -v "$PWD:/src:ro" -w /src semgrep/semgrep semgrep scan --config p/default --error` |
| Image scan | Trivy on the built `api` and `web` images: fixable HIGH/CRITICAL vulnerabilities and baked-in secrets | `docker build`, then `trivy image` |
| Dockerfile checks | Trivy misconfiguration scan | `trivy config .` |
| Workflow checks | actionlint and zizmor on the workflow files | `actionlint`, `zizmor .github` |
| **CI passed** | fails unless every job above succeeded | |

**Branch protection (owner action).** After the first run, in GitHub go to **Settings > Branches** and
protect `main`: require a pull request and require the single status check **CI passed**.

**Weekly security scan.** `.github/workflows/security.yml` runs the OWASP ZAP baseline (passive, no
attacks) against **staging only** every Monday and on demand. Set the repository **variable** (not a
secret) `STAGING_URL` once staging exists; until then the run ends with a visible warning and scans
nothing. The workflow refuses any URL that is not `https://` with a `staging` label in the host name.
Rule levels are in `.zap/rules.tsv`.

**Pins.** Third-party actions are pinned to a commit SHA, and the scanners run as containers pinned
by digest, so a tag cannot be moved under us. Dependabot (`.github/dependabot.yml`) opens one grouped
pull request per ecosystem each week for Python (uv), npm (pnpm), Docker, Docker Compose and Actions,
and only proposes releases that are at least 14 days old. The scanner digests in `ci.yml` are not
visible to Dependabot: refresh them by hand about once a month (the comment above them says how).

**Dependency cooldown.** Both lockfiles refuse releases younger than 14 days
(`web/pnpm-workspace.yaml` `minimumReleaseAge`, `api/pyproject.toml` `exclude-newer`). A security fix
inside the window is let through by name with `exclude-newer-package`, with a comment saying when to
remove it.

## Licence

Proprietary. All rights reserved.
# hrcmr
