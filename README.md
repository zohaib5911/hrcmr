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

Docker (with Compose), Node.js 24 and pnpm, Python 3.12 with `uv`, and git. Commands for
running the local stack, the tests and the deployment are added to this file by the tasks
that create them (local stack, API, web, CI and deployment).

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
