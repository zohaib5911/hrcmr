# Architecture

Summary of the system as specified in `plan.md` sections 2 to 4. This file is updated
whenever a task changes a boundary described here.

## Services

| Service | Technology | Role |
|---|---|---|
| `web` | Next.js 16 (App Router), React, TypeScript | Public website, company app, super-admin UI. Holds no third-party secrets. |
| `api` | Python 3.12, FastAPI, SQLAlchemy 2 (async), Pydantic v2 | All business logic and all calls to third parties (Stripe, Resend, Anthropic, R2, Companies House). |
| `worker` | ARQ on Redis | Background jobs and the cron schedule (reminders, imports, backups, purges). |
| `clamav` | clamd | Malware scanning of every upload. Private network only. |
| `postgres` | PostgreSQL 16 with pgvector | System of record. Row-level security on every tenant table. |
| `redis` | Redis 7 | Sessions, rate limits, job queue, cache. |

Hosting is Railway (EU West, Amsterdam) with two environments, `staging` and `production`.
Cloudflare provides DNS, TLS, CDN, WAF, Turnstile and R2 object storage (EU jurisdiction,
private buckets).

## Hosts

| Host | Served by | Content |
|---|---|---|
| `DOMAIN` | `web` | Marketing site and the signed-in company app |
| `admin.DOMAIN` | `web` | Super-admin route group (Platform Admins only) |
| `api.DOMAIN` | `api` | JSON API at `/api/v1` |
| `staging.DOMAIN`, `api.staging.DOMAIN`, `admin.staging.DOMAIN` | as above | Staging equivalents |

## Trust boundaries

1. **Browser to `web` / `api`.** Untrusted. Sessions are opaque tokens in an HttpOnly cookie;
   every state-changing request carries a CSRF token. Only allow-listed, non-secret
   `NEXT_PUBLIC_*` values reach the browser.
2. **`web` to `api`.** `web` calls the API over the private network (`API_INTERNAL_URL`) and
   never talks to third-party services.
3. **`api` / `worker` to data stores.** Postgres and Redis are reachable only over Railway
   private networking. The API connects as `app_user`, which cannot bypass row-level
   security; migrations run as `app_owner`.
4. **`api` to third parties.** Server-side only, with scoped credentials: a restricted Stripe
   key, single-bucket R2 tokens, a sending-only Resend key. Outbound AI requests carry no
   restricted personal data (plan section 8.12).

## Tenant isolation

Every tenant table carries `company_id`. Isolation is enforced twice: the application
injects `company_id` through a tenant-scoped session, and Postgres row-level security
checks `company_id = current_setting('app.company_id')::uuid` per transaction. Super-admin
access uses a separate database role and is fully audited.

## Data protection

Sensitive fields (National Insurance, passport, bank details, share codes, CoS numbers,
TOTP secrets) are encrypted with AES-256-GCM using versioned keys and are masked by
default. The `audit_events` table is append-only. Uploaded files are validated, scanned
and stored in private R2 buckets under random keys, and downloaded through 60-second
presigned URLs.
