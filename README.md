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
| `redis` | `localhost:6379` | Railway Redis | Sessions, rate limits, job queue. |
| `rustfs` | S3 API `http://localhost:9000`, console `http://localhost:9001` | Cloudflare R2 | Private bucket `files-dev` is created by the one-shot `rustfs-init` job, which then exits (that is normal). |
| `mailpit` | SMTP `localhost:1025`, inbox `http://localhost:8025` | Resend | Catches every e-mail. Nothing leaves your machine. |
| `clamav` | `localhost:3310` | ClamAV on Railway | First start downloads about 300 MB of signatures and takes several minutes; needs about 1.5 GB RAM. Signatures are kept in a volume, so later starts are quick. |
| `stripe-cli` | none | Stripe webhooks | Off by default; see below. |

All ports are bound to `127.0.0.1`. The local credentials (`postgres`/`postgres` for Postgres,
`rustfsadmin` for RustFS) protect throwaway containers only. Override any of them, or any port
(`POSTGRES_PORT`, `REDIS_PORT`, `S3_PORT`, `S3_CONSOLE_PORT`, `MAILPIT_SMTP_PORT`,
`MAILPIT_UI_PORT`, `CLAMAV_PORT`), in a local `.env`. If you change `RUSTFS_ACCESS_KEY` or
`RUSTFS_SECRET_KEY`, set `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY` to the same values.

**Stripe webhooks (from Phase 16).** Put a Stripe **test-mode** key in your own `.env` as
`STRIPE_SECRET_KEY`, run `docker compose --profile stripe up -d stripe-cli`, then read the webhook
signing secret from `docker compose logs stripe-cli` and put it in `.env` as
`STRIPE_WEBHOOK_SECRET`. Do not paste either value into chat.

**Why RustFS and not MinIO?** The plan named MinIO as the local stand-in for R2. Its community
project has been archived and its Docker images withdrawn, so RustFS (Apache-2.0, S3-compatible)
was chosen with the owner's approval. Production still uses Cloudflare R2.

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

## Licence

Proprietary. All rights reserved.
# hrcmr
