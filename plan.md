# plan.md — UK HR & Sponsor Compliance Platform (complete build plan)

> **Audience:** Claude Code.
> **Starting point:** an empty folder.
> **End point:** a secure, production-deployed web platform. It reproduces every feature of the reference product (MadyHR.ai, scanned on 31 Oct and 1 Nov 2026) and adds an Apple-quality design, a Sponsorship Job Checker (SOC finder) and a super-admin back office.
>
> **Read this whole file before writing any code. Then work strictly task by task, in order.**

---

## 0. How you (Claude Code) must work — read first, follow always

### 0.1 Working rules
1. **One task at a time.** Do tasks in the exact order of Section 9 (T0.1, T0.2, …). Never start a task until the previous one is finished and its "Done when" checks pass.
2. **Keep a progress log.** Create `PROGRESS.md` in T0.1. After every task, tick it and write one line on what was done, and anything the owner must do. Before starting each task, re-read `PROGRESS.md` and that task.
3. **Commit after every task** with a Conventional Commit message such as `feat(leave): add balances ledger (T8.2)`. Never commit secrets (Section 4).
4. **Tests are part of the task.** Each task lists checks. Run lint, type-check and tests. A task with failing checks is not done.
5. **No placeholders left behind.** Leave no `TODO`, no lorem ipsum, no fake data in production code paths, and no commented-out code. Seed and demo data lives only in `seed/` and runs only in development.
6. **Ask the owner only when blocked by something you cannot create yourself.** That means a secret or key, an account, a DNS record, a legal text decision or a payment. Write the request into `PROGRESS.md` under "Owner actions needed". Carry on with any later task that does not depend on it. If none can proceed, stop and summarise.
7. **Never invent legal, tax or immigration figures.** Every rate, threshold or rule comes from an official source (GOV.UK, legislation.gov.uk, HMRC, ACAS, ONS, Home Office). Store each with its source URL and the date you checked it. If you cannot verify a figure, mark it `UNVERIFIED` and list it in `PROGRESS.md`.
8. **Original content only.**
   - Do not copy text, images, logos, screenshots, course content or page copy from MadyHR.ai or any other product.
   - Rebuild **features and behaviour**. Write all copy fresh.
   - The brand name, logo and colours come from `brand.config.ts`. The default name is the placeholder **"Brand"**; the owner will change it later.
   - Do not use Apple's trademarks, logos, SF Symbols, or Apple device images. "Apple-like" means the design quality and principles in Section 5, not Apple assets.
9. **Design quality gate.** Every screen must pass the Design QA checklist (Section 5.12) before its task is done. That means Playwright screenshots in light, dark, mobile and desktop.
10. **Accessibility.** Meet WCAG 2.2 AA: keyboard reachable, visible focus, labels, contrast, reduced motion.
11. **Keep everything typed.** TypeScript `strict`, mypy `strict` for the API, and Pydantic schemas for every request and response. Generate a typed TypeScript API client from the FastAPI OpenAPI schema. In production, OpenAPI docs are served **only** to authenticated super-admins.
12. **Phase gates.** At the end of each phase:
    - run the full test suite;
    - write a short phase summary in `PROGRESS.md`, including screenshots saved to `docs/screenshots/<phase>/`;
    - check that nothing from earlier phases has broken.

### 0.2 Definition of Done (applies to every task)
- The feature works end to end (UI → API → DB) for every role allowed to use it, and is refused for roles that are not (test both).
- Tenant isolation test passes: a user of company A can never read or write company B's data.
- Every state-changing action that touches Right to Work, salary, permissions, sponsor documents, status or deletion writes an **audit event** in the same DB transaction.
- Loading, empty, error and success states are all designed.
- The screen is responsive from 360 px to 1920 px and works in light and dark mode.
- Unit, API and (for key flows) Playwright end-to-end tests are written and green.
- No secret values appear in the code, logs, test snapshots, screenshots or commits.

---

## 1. What we are building (product summary)

A UK HR and **sponsor-licence compliance** SaaS for small employers. It does **not** run payroll; it works alongside the customer's existing payroll provider.

**Pricing (configurable via Stripe price IDs):**
- **Free plan:** never expires. Read-only once nothing is paid, and employees cannot be added.
- **Annual:** £50 a year.
- **10-year:** £240 paid once.
- Unlimited employees on every plan. 14-day money-back guarantee with an automatic refund.
- When a paid plan ends, the account becomes read-only. Nothing is deleted.

**Three panels, one codebase:**
1. **Employee self-service:** My Leave, My Approvals, My Shifts, My Work Log, My Learning, My Documents, My Profile, plus clock in/out.
2. **Company admin app:** Dashboard, Employees, Recruitment, Org Chart, Sponsor Compliance, Documents, Policies & Sign-offs, Learning, Leave, Attendance, Rota, Work Log, Holidays, Sponsorship Job Checker (new), Company settings (16 pages), User Access, Billing.
3. **Super-admin back office** (our own team): companies, subscriptions, refunds, support impersonation, deletion queue, rules-data updates (SOC and salary lists), content (courses, templates, guides), announcements, jobs, metrics, audit.

**Public website:**
- Marketing pages, pricing and security.
- 14 free calculators, guides and templates.
- Public careers pages per company.
- Training certificate verification.
- A free **UK sponsor licence register**: daily data, map, change bulletins and roughly 128k sponsor profile pages.
- Legal pages and a contact form.

**Roles (fixed system roles):** Company Admin, HR Admin, People Manager, Recruiter, Employee, Read-only Auditor, plus our internal **Platform Admin** (super-admin, separate).

---

## 2. Technology stack (final — do not change without asking)

| Area | Choice |
|---|---|
| Frontend + public site | **Next.js 16 (App Router), React, TypeScript strict**, pnpm |
| UI | **Tailwind CSS v4 + shadcn/ui (Radix primitives)**, fully re-themed to Section 5 |
| Motion | **Framer Motion** (springs, respects `prefers-reduced-motion`) |
| Icons | **Lucide** (1.5 px stroke) |
| Charts | Recharts (styled to Section 5) |
| Forms | react-hook-form + zod (zod schemas generated from the OpenAPI types where possible) |
| Data fetching | TanStack Query + generated typed client (`openapi-typescript` + `openapi-fetch`) |
| Backend API | **Python 3.12 + FastAPI**, uvicorn/gunicorn |
| ORM / migrations | **SQLAlchemy 2.0 (async) + Alembic** |
| Validation | **Pydantic v2**, pydantic-settings (`SecretStr` for every secret) |
| Background jobs | **ARQ** on Redis (worker + cron schedule) |
| Database | **PostgreSQL 16** (UUID v7 primary keys, `pg_trgm`, `pgvector`, `unaccent`) |
| Cache / sessions / queue | **Redis 7** |
| File storage | **Cloudflare R2** (S3 API, EU jurisdiction bucket, private) |
| Malware scan | **ClamAV** (clamd container) |
| Email | **Resend** (React Email templates rendered server-side by the API worker via MJML or Jinja) |
| AI | **Anthropic Claude API**. Model names come from environment variables: `ANTHROPIC_MODEL_MAIN` (default `claude-sonnet-5-5`), `ANTHROPIC_MODEL_FAST` (default `claude-haiku-5-5`) |
| Embeddings (SOC finder) | Local embedding model via `fastembed` (e.g. `BAAI/bge-small-en-v1.5`) stored in pgvector, so no extra paid API |
| Payments | **Stripe** (Checkout, Billing Portal, Refunds, Webhooks) |
| Bot protection | **Cloudflare Turnstile** on public forms (signup, login after failures, contact, careers apply, forgot password) |
| PDFs | WeasyPrint (server) |
| Excel | openpyxl |
| Error tracking | Sentry (with PII scrubbing) |
| Hosting | **Railway, EU West (Amsterdam)**: services `web`, `api`, `worker`, `clamav`, `postgres`, `redis`; two environments, **staging** and **production** |
| Edge | **Cloudflare**: DNS, TLS, CDN, WAF, R2 |
| CI | **GitHub Actions** (private repo) |
| Local dev | Docker Compose: postgres, redis, minio (stands in for R2), mailpit (stands in for Resend), clamav, stripe-cli |
| Tests | pytest + pytest-asyncio + httpx, factory-boy; Vitest; Playwright (+ axe-core) |
| Quality | ruff, mypy, eslint, prettier, gitleaks, semgrep, pip-audit, pnpm audit, Trivy |

---

## 3. Repository layout (create exactly this)

```
/
├─ PROGRESS.md
├─ README.md                      # how to run locally, test, deploy
├─ SECURITY.md                    # security policy + how to report
├─ .env.example                   # variable NAMES only, no values (see deployment-requirements.txt)
├─ .gitignore                     # includes .env, .env.*, !.env.example, *.pem, *.key, /secrets
├─ .gitleaks.toml
├─ .pre-commit-config.yaml        # gitleaks, ruff, prettier, eslint
├─ docker-compose.yml
├─ brand.config.ts                # name, tagline, logo paths, colours (placeholder "Brand")
├─ docs/
│  ├─ architecture.md
│  ├─ data-model.md               # generated from models
│  ├─ security.md
│  ├─ runbooks/                   # key rotation, restore backup, incident response, rules-data update
│  └─ screenshots/
├─ web/                           # Next.js app (public site + company app + super-admin)
│  ├─ app/
│  │  ├─ (marketing)/             # public pages
│  │  ├─ (auth)/                  # login, setup, forgot/reset, verify, mfa, accept-invite
│  │  ├─ (app)/                   # signed-in company app
│  │  ├─ (admin)/                 # super-admin, only on admin host
│  │  ├─ careers/[company]/       # public careers
│  │  └─ sponsors/                # public register
│  ├─ components/ui/              # design-system primitives (Section 5)
│  ├─ components/app/             # app-specific composites
│  ├─ lib/api/                    # generated client + query hooks
│  ├─ lib/permissions.ts          # mirrors API permission strings for UI gating ONLY
│  ├─ content/                    # original guides/templates (MDX) with source metadata
│  ├─ rates/                      # calculator rates JSON with sources (Section 10)
│  ├─ middleware.ts               # host routing, security headers, nonce CSP
│  └─ tests/ (vitest + playwright)
├─ api/                           # FastAPI
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ core/ (config, security, crypto, sessions, rbac, tenancy, audit, errors, logging, ratelimit)
│  │  ├─ db/ (base, session, rls)
│  │  ├─ modules/<module>/ (models.py, schemas.py, service.py, router.py, tests/)
│  │  ├─ integrations/ (r2.py, resend.py, stripe.py, anthropic.py, clamav.py, turnstile.py, govuk.py)
│  │  ├─ jobs/ (arq worker, cron)
│  │  └─ ai/ (ask_mady tools, redaction, prompts)
│  ├─ alembic/
│  ├─ seed/                       # dev-only demo data + reference data loaders
│  └─ tests/
├─ data/                          # reference data sources + import scripts (ONS SOC index, rules tables)
└─ .github/workflows/ (ci.yml, deploy-staging.yml, deploy-production.yml, security.yml)
```

**Hosts:**
- `DOMAIN` (marketing and company app, served by `web`)
- `api.DOMAIN` (FastAPI)
- `admin.DOMAIN` (the super-admin route group, served by `web`; `middleware.ts` only allows `(admin)` routes on this host)
- `staging.DOMAIN` / `api.staging.DOMAIN` / `admin.staging.DOMAIN`

---

## 4. Security — non-negotiable rules (secrets, data, clients)

### 4.1 Secrets: never exposed, ever
1. **Secrets live only in:**
   - Railway environment variables (staging and production);
   - the owner's local `.env`, which is gitignored and never read aloud;
   - GitHub Actions encrypted secrets (only `RAILWAY_TOKEN_*` and `SENTRY_AUTH_TOKEN`).
2. **Never** print, echo, log, paste into chat, write to files or include in error messages any secret value. When you need to confirm a variable exists, check only that it is set (`bool(os.environ.get(...))`).
3. **Code layout:**
   - `.env.example` contains **names only**.
   - pydantic-settings loads secrets as `SecretStr`, so its `repr` shows `**********`.
   - Use `get_secret_value()` only inside integration clients.
4. **The browser never receives a secret.**
   - Only variables prefixed `NEXT_PUBLIC_` reach the browser. The allowed list is in `deployment-requirements.txt`, and they are all non-secret (public URLs, Stripe **publishable** key, Turnstile **site** key, Sentry public DSN).
   - A CI check fails the build if any other `NEXT_PUBLIC_*` variable appears.
   - Every call to Stripe, Resend, Anthropic, R2 or Companies House is made **server-side from FastAPI**, never from Next.js route handlers or the browser.
   - Next.js server code must not hold third-party secrets either. Its only server-only values are `SESSION_COOKIE_NAME` and `API_INTERNAL_URL`, and neither is secret.
5. **Scanning and CI guards:**
   - `gitleaks` runs in pre-commit **and** CI, and blocks any commit containing a secret.
   - `semgrep` rules flag hard-coded credentials.
   - Add a CI test that greps the built `.next/static` bundle for known secret prefixes (`sk_live`, `sk_test`, `rk_`, `re_`, `sk-ant-`, `whsec_`) and fails if found.
6. **Separate keys:** use different keys for staging and production. Stripe uses a **restricted key**, given only the permissions needed. R2 API tokens are scoped to a single bucket each.
7. **Encryption keys:**
   - `FIELD_ENCRYPTION_KEYS` is JSON `{ "k1": "<base64 32 bytes>" }`, with `FIELD_ENCRYPTION_ACTIVE_KID`.
   - `BLIND_INDEX_KEY` and `SESSION_SECRET` are generated by the owner (instructions in `deployment-requirements.txt`).
   - Support key rotation (re-encrypt job) and document it in `docs/runbooks/key-rotation.md`.
8. **Sentry:** `send_default_pii=False`, plus a `before_send` scrubber that removes cookies, authorization headers, request bodies and any field in the sensitive list.

### 4.2 Authentication and sessions
- **Passwords:**
  - argon2id hashes (memory 64 MB, iterations 3, parallelism 4).
  - Minimum 12 characters.
  - Block common or breached passwords using the HIBP k-anonymity range API, falling back to a local top-100k list.
- **Sessions:**
  - The session is an opaque random 256-bit token in an `HttpOnly; Secure; SameSite=Lax; Path=/` cookie on the parent domain (`Domain=.DOMAIN`). The token is stored server-side as a **SHA-256 hash** in Redis, with a Postgres record for the audit trail.
  - Idle timeout 8 h; absolute timeout 14 days.
  - Rotate the session on login, MFA completion and privilege change.
- **CSRF:** SameSite=Lax **plus** a double-submit CSRF token (`X-CSRF-Token` header, which must match a non-HttpOnly `csrf` cookie) on every state-changing request.
- **CORS:** allow only `https://DOMAIN` and `https://admin.DOMAIN` (and the staging equivalents), with credentials true. Never use a wildcard.
- **MFA:**
  - TOTP (RFC 6238) with 10 single-use recovery codes, stored hashed.
  - Company MFA policy: optional / required for Company Admins / required for all.
  - **Platform Admins must use MFA; it cannot be turned off.**
- **Step-up re-authentication (password or TOTP within the last 10 minutes)** is required to:
  - reveal NI, passport or bank numbers;
  - change roles;
  - invite admins;
  - start account deletion;
  - change the billing plan.
- **Invitations:** single-use link tokens (hashed, 72 h expiry). This is an **improvement on the reference**, which emails no link and makes the admin share an initial password. Users set their own password; the admin never sees it.
- **Email verification** is required before a company can do anything beyond setup.
- **Rate limits (Redis):**
  - login 5 per minute per IP and 10 per hour per account, with progressive lockout and a notification email;
  - password reset 3 per hour per email;
  - signup 5 per hour per IP plus Turnstile;
  - AI 30 per hour per user;
  - public APIs 60 per minute per IP.
- **Account enumeration:** login, reset and signup give identical responses and timing whether or not the email exists.

### 4.3 Tenant isolation (client data must never leak)
1. Every tenant table has `company_id UUID NOT NULL`, indexed.
2. **Application layer:** all queries go through a `TenantSession` that injects `company_id` automatically. Raw queries are forbidden outside `db/`.
3. **Database layer (defence in depth):** enable **Postgres Row-Level Security** on every tenant table, with the policy `company_id = current_setting('app.company_id')::uuid`.
   - The API runs as a **non-owner role** `app_user` that cannot bypass RLS.
   - Migrations run as `app_owner`.
   - `SET LOCAL app.company_id` is applied per transaction.
4. Super-admin access uses a separate role, `platform_admin_rw`, only from the admin router. Every read or write it makes is audited.
5. **Automated isolation tests:** for every router, create two companies and assert a 404 (not 403, so existence isn't revealed) for cross-tenant IDs.
6. IDs are UUIDs; nothing is guessable. Public pages use random slugs.

### 4.4 Authorization (RBAC)
- Permissions are strings `module.screen.action`, optionally ending in `_own` or `_reports` (full list in Section 7).
- Every endpoint declares its permission with `Depends(require("leave.request.approve"))`.
- `_own` means the record belongs to the linked employee.
- `_reports` means the record belongs to someone whose Reporting Authority, directly or indirectly, is the user's linked employee. Leave approvals use the **Leave Sanctioning Authority** relationship instead.
- The UI hides what the user can't use, but **the server is the only enforcement point**.

### 4.5 Data protection
- **Field-level encryption** (AES-256-GCM, random 96-bit nonce, key id prefix) for:
  - NI number, passport number, bank sort code and account number (employee and company);
  - visa or eVisa reference, share codes, CoS number;
  - TOTP secrets.
- Searchable equality uses an HMAC-SHA256 **blind index** (for example, to find duplicate NI numbers).
- **Masking:** the API returns masked values (`•••• ••• 12 C`) by default. Revealing requires the permission, step-up, and an audit event with a reason.
- **Health data:** sickness records count as special category data. Restrict them to roles with `attendance.record.read` / `leave.request.read`. Never send them to AI.
- **File uploads:**
  - stream through the API;
  - check the size limit (25 MB), an extension allowlist (pdf, jpg, jpeg, png, doc, docx, xlsx, csv) **and the magic-byte MIME**;
  - scan with ClamAV, and reject if infected or if scanning fails (fail closed);
  - store in R2 under a random key `company/<company_id>/<uuid>`;
  - downloads use presigned GET URLs valid for **60 seconds**, with `Content-Disposition: attachment` and the original filename sanitised;
  - nothing in R2 is public.
- **Audit log:**
  - The `audit_events` table is **append-only**: a DB trigger raises on UPDATE or DELETE, and the API role has no UPDATE or DELETE grant on it.
  - Each event stores: actor, company, action, entity, before and after (sensitive fields masked), IP, user agent, request id, reason and timestamp.
- **Backups:** Railway Postgres backups, plus a nightly encrypted `pg_dump` (age-encrypted with the owner's public key) to a separate R2 backup bucket with 35-day retention. Test restore monthly; the runbook is `docs/runbooks/restore.md`.
- **Retention:**
  - Right to Work evidence is kept for employment + 2 years, then purged by a scheduled job.
  - Sponsor records are kept for sponsorship + 1 year.
  - Deleted companies are purged within 7 days of a confirmed request.
  - Session logs 90 days; AI prompt logs 30 days (metadata only).
- **AI privacy:** see Section 8.12. NI numbers, bank details, passport and visa numbers, share codes, health details and salary are **never** sent. Employee names are replaced with labels.

### 4.6 Web security headers and hardening
- **CSP** with per-request nonce: `default-src 'self'`; scripts limited to self, the nonce and Stripe/Turnstile domains; `frame-ancestors 'none'`; `object-src 'none'`; `base-uri 'self'`; `form-action 'self'`. Third-party marketing pixels load only after cookie consent, and only on marketing routes.
- `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy`: disable camera, microphone and geolocation, except geolocation is self-only and opt-in on the clock-in page.
- The `X-Frame-Options: DENY` header is set.
- Cloudflare WAF with managed rules on, bot-fight mode on, and rate limiting for `/api/v1/auth/*`.
- **Stripe webhooks:** verify the signature with `STRIPE_WEBHOOK_SECRET`, keep idempotency keys, and store processed event ids.
- **Dependency scanning:** Dependabot weekly, plus `pip-audit`, `pnpm audit`, Trivy for images and `semgrep` in CI.
- Postgres and Redis are reachable **only via Railway private networking**, never through public proxies in production.
- The super-admin host requires a Platform Admin with MFA. An optional IP allowlist uses `ADMIN_IP_ALLOWLIST`.
- **Logging:** structured JSON logs (structlog) with a request id. A redaction processor drops keys matching `password|token|secret|authorization|cookie|ni_number|passport|sort_code|account_number|share_code|cos_number|salary|bank`.

### 4.7 Security tests (must exist and pass)
- Tenant isolation suite (every router).
- RBAC matrix test: every role against every endpoint, comparing expected allow or deny with Section 7.
- Auth tests: lockout, session rotation, CSRF rejection, MFA required by policy, step-up enforcement, invitation expiry.
- Upload tests: oversize, wrong magic bytes, EICAR test file is rejected.
- Secret-leak test: built frontend bundle and API OpenAPI schema contain no secrets.
- Webhook signature test.
- An OWASP ZAP baseline scan against staging, run in the `security.yml` workflow.

---

## 5. Design system — "designed like Apple" (quality bar for every pixel)

The aim is the calm, precise, generous feel of Apple's own software and product pages, built from **our own** tokens and components. Use no Apple assets.

### 5.1 Principles
1. **Clarity:** one primary action per view, plain language, and numbers people can act on ("1 check expires in 21 days", not "Status: warning").
2. **Deference:** the content is the hero. Use quiet chrome, hairline separators, plenty of white space and few borders.
3. **Depth:** translucent materials for sidebar, toolbar and sheets, soft layered shadows, and motion that explains where things come from.
4. **Consistency:** the same component everywhere for the same job. Never build a one-off.
5. **Craft:** pixel-aligned to a 4 px grid, optical alignment of icons, no layout shift, 60 fps animations.

### 5.2 Typography
- **Font stack:** `-apple-system, BlinkMacSystemFont, "Inter var", "Inter", system-ui, "Segoe UI", Roboto, sans-serif`. Self-host **Inter var** via `next/font` as the cross-platform fallback. Never bundle Apple's SF fonts; the system stack shows SF natively on Apple devices.
- Numbers use `font-variant-numeric: tabular-nums` in tables, KPIs and timers.

**App type scale (px / line-height / weight / tracking):**

| Style | Size | Line height | Weight | Tracking |
|---|---|---|---|---|
| Large Title | 34 | 41 | 700 | -0.4 |
| Title 1 | 28 | 34 | 700 | -0.4 |
| Title 2 | 22 | 28 | 600 | -0.3 |
| Title 3 | 20 | 25 | 600 | -0.2 |
| Headline | 15 | 20 | 600 | -0.1 |
| Body | 15 | 22 | 400 | 0 |
| Callout | 14 | 20 | 400 | 0 |
| Subheadline | 13 | 18 | 400 | 0 |
| Footnote | 12 | 16 | 400 | 0 |
| Caption | 11 | 13 | 500 | 0.1 |

**Marketing type scale:**
- Hero: 64–80 px, weight 700, tracking -0.03em, line height 1.05.
- Section titles: 40–48 px.
- Body: 19–21 px, line height 1.5.
- All of these scale down for mobile with `clamp()`.

### 5.3 Colour tokens
Define these as CSS variables in `web/app/globals.css`, with light and dark values. Every pair must pass WCAG AA (4.5:1 for text, 3:1 for UI).

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | #F5F5F7 | #000000 | app canvas |
| `--bg-elevated` | #FFFFFF | #1C1C1E | cards, sheets |
| `--bg-grouped` | #F2F2F7 | #000000 | settings-style grouped lists |
| `--fill-secondary` | rgba(120,120,128,0.12) | rgba(120,120,128,0.24) | inputs, segmented track |
| `--label` | #1D1D1F | #F5F5F7 | primary text |
| `--label-secondary` | #6E6E73 | #A1A1A6 | secondary text |
| `--label-tertiary` | #86868B | #6E6E73 | hints (large text only) |
| `--separator` | rgba(60,60,67,0.18) | rgba(84,84,88,0.6) | hairlines |
| `--accent` | #0071E3 | #2997FF | primary buttons, links, focus |
| `--accent-pressed` | #0062C4 | #0A84FF | pressed |
| `--success` | #248A3D (text) / #34C759 (fill) | #30D158 | verified, present |
| `--warning` | #B25000 (text) / #FF9F0A (fill) | #FFD60A | expiring, due |
| `--danger` | #D70015 (text) / #FF3B30 (fill) | #FF453A | expired, failed, overdue |
| `--info` | #0071E3 | #64D2FF | neutral notices |
| `--sidebar-material` | rgba(246,246,248,0.72) + blur | rgba(28,28,30,0.72) + blur | sidebar/toolbar |

- **Status chips:** a soft fill of the status colour at 12–15% opacity, with the text colour from the table above.
- **Brand colour:** `brand.config.ts` may override `--accent` only. All other tokens stay as above.
- **Dark mode:** follows the system setting by default. Users can override it in My Profile (stored in a cookie). Use the `data-theme` attribute plus `prefers-color-scheme`.

### 5.4 Materials, radius, elevation, spacing
- **Materials:**
  - Sidebar and top toolbar: `backdrop-filter: saturate(180%) blur(20px)` over `--sidebar-material`.
  - Sheets and popovers: `--bg-elevated` at 92% plus a blur.
  - Fall back to solid colours when `backdrop-filter` is unsupported or reduced transparency is preferred.
- **Radius:** controls 10 px, cards 16 px, sheets and dialogs 20 px, popovers 14 px, chips and pills 999 px, avatars round.
- **Elevation** (soft and layered):
  - `e1`: 0 1px 2px rgba(0,0,0,.04), 0 1px 1px rgba(0,0,0,.02)
  - `e2`: 0 4px 12px rgba(0,0,0,.06), 0 1px 3px rgba(0,0,0,.04)
  - `e3` (sheets): 0 20px 50px rgba(0,0,0,.12), 0 4px 12px rgba(0,0,0,.06)
  - In dark mode use borders `rgba(255,255,255,.08)` instead of shadows.
- **Spacing:** 4 px base. Page padding is 32 px on desktop and 16 px on mobile. Section gap is 24–32 px. Content max width is 1200 px in the app and 1120 px for marketing text.
- **Hit targets:** at least 44 × 44 px on touch and 32 px on desktop.

### 5.5 Motion
- **Default spring:** `{ type: "spring", stiffness: 420, damping: 34, mass: 0.9 }`
- **Durations:** micro 120 ms, small 200 ms, sheets 320 ms.
- **Behaviour:**
  - Sheets rise from the bottom on mobile and scale from 0.96 plus fade on desktop.
  - Sidebar collapse animates width.
  - List rows animate layout on insert and delete (`layout` prop).
  - Numbers in KPI cards count up once on first view.
  - Skeleton shimmer is subtle.
- With `prefers-reduced-motion`, replace movement with opacity fades only.

### 5.6 Layout of the signed-in app
- **Sidebar** (translucent, 260 px wide, collapsible to 72 px with `[`):
  - grouped sections with small-caps captions: OVERVIEW · PEOPLE · COMPLIANCE · TIME · ME · COMPANY;
  - each row has an icon and label, plus a count badge where useful (approvals, due reminders);
  - the active row has an accent-tinted pill;
  - the company switcher sits at the top (logo, name, plan pill);
  - the user card sits at the bottom.
- **Toolbar** (56 px, translucent, sticky):
  - left: page title (Title 2) with breadcrumbs above it in Footnote;
  - centre: search field (rounded, `⌘K` hint);
  - right: help `?`, notifications bell (with badge), avatar menu.
- **Content:** Large Title header with a one-line description, and the primary action as a filled accent button on the right with at most two secondary actions. Below that comes the content.
- **Inspector drawer:** a right-hand sheet, 440 px wide, for record previews such as a person's summary from the org chart, a reminder review, or a leave request decision. It keeps the user's place in the list.
- **Settings pages** use the **inset grouped list** pattern (like a system settings app):
  - grouped white rounded sections on a `--bg-grouped` canvas;
  - rows have a label on the left, the value or a chevron on the right, and hairline separators inset 16 px;
  - edit happens in a sheet.
- **Mobile (<768 px):**
  - the sidebar becomes a bottom tab bar (Home, People, Compliance, Time, Me) plus a "More" sheet;
  - tables become stacked cards;
  - dialogs become bottom sheets with a grabber.

### 5.7 Component library (build once in `web/components/ui/`, use everywhere)
| Category | Components |
|---|---|
| Buttons | Button (variants: filled, tinted, gray, plain, destructive; sizes: sm, md, lg; loading state with spinner and kept width), IconButton |
| Inputs | TextField (floating hint, inline validation, clear button), SearchField (rounded), TextArea (auto-grow), Select (native on mobile), Combobox (async search), DatePicker and DateRangePicker (calendar popover, keyboard entry, UK format DD MMM YYYY), TimePicker, NumberField (currency and hours units), Toggle (switch), Checkbox, Radio cards (title + description, used for roles, check types and policy confirmation modes), FileDrop (drag area, progress, scan status "Scanning… / Safe / Rejected") |
| Navigation | SegmentedControl (Calendar / Requests / Balances; Day / Week / Month / Custom), Tabs (underline style for record tabs) |
| Containers | Card (with header, actions and footer slots), Sheet, Dialog, ConfirmDialog (destructive confirmations require typing the record name for deletions), InlineConfirm (as on employee status change), Popover, Menu/ContextMenu, Tooltip |
| Feedback | Toast (top-centre banner on desktop, top on mobile; undo action where reversible), Alert/Banner (info, warning, danger, success), EmptyState (glyph, title, one sentence, primary action), Skeletons per layout, ErrorState (retry, request id), ProgressRing, ProgressBar, Stepper (for wizards and the recruitment pipeline) |
| Data | Badge/StatusChip (Verified, Expiring, Expired, Pending, Not recorded, Draft, Open, Closed…), Avatar (initials with deterministic soft colour) and AvatarStack, KPI Card (label, big number, sub-label, optional sparkline, link), DataTable (sticky header, sortable, column visibility, row selection, keyboard J/K/Enter, pagination or virtualisation over 200 rows, density toggle, CSV/XLSX export hook, responsive card mode), Timeline (history, audit, application stages), CalendarMonth (leave), WeekGrid (rota), OrgChart canvas, Charts (bar, donut, line) themed with tokens |
| Global | CommandPalette (Spotlight-style: recents, pages, people, actions), KeyboardShortcutsSheet, AskMadyPanel (assistant side sheet with suggestion chips, streaming answer, sources line, "AI-generated from your records" footnote; the assistant name is configurable in `brand.config.ts`, default "Assistant") |

### 5.8 Content and voice
- Write in UK English, sentence case and plain words. Use the second person ("your Company").
- Dates are shown as `1 Nov 2026`; times as 24 h `09:00`; money as `£41,700`.
- Empty states explain what will appear and the one action that makes it appear.
- Errors say what happened and how to fix it. Never show a stack trace; show a request id.
- Every legal or immigration tool shows "General guidance, not legal advice" and the sources with the date checked.

### 5.9 Marketing site style
- Sticky translucent header with a sticky local section nav on long pages.
- Huge headline, short sub-head and one CTA pair (filled + plain).
- Product shots are **real screenshots of our app** with seeded demo data, in a neutral generic browser or laptop frame (not Apple devices). They have a soft shadow and parallax/scroll-reveal at 8–16 px max.
- Alternating full-bleed sections in white and #F5F5F7, with centred copy at 720 px max and feature grids of 3 or 4 tiles with icons.
- The pricing section has two large cards (10-year highlighted with a "Best value" pill) and a live headcount slider showing price per person.
- Footer has 4 columns (Product, Resources, Company, Legal), a small legal line, and registration numbers from `brand.config.ts`.

### 5.10 Iconography and illustration
- Lucide icons at 1.5 px stroke, sized 16/20/24, with consistent mapping (for example Shield = compliance, Users = people, CalendarDays = leave, Clock = attendance, LayoutGrid = rota).
- Empty-state glyphs are simple line icons inside a 64 px soft circle.
- No stock photos in the app. Marketing may use one abstract gradient per page, generated with CSS.

### 5.11 Data visualisation rules
- Use a maximum of 5 colours from the tokens. Label values directly where possible, give axes light gridlines, and use tooltips with tabular numbers.
- Never use colour alone to convey state; always include a text label.

### 5.12 Design QA checklist (run per screen; save screenshots to `docs/screenshots/`)
- [ ] Light and dark; 390 px, 768 px, 1280 px, 1920 px.
- [ ] Spacing on the 4 px grid; text aligns to a single left edge; no orphan or widow words in headings.
- [ ] One primary action; the destructive action is separated and confirmed.
- [ ] Loading skeleton matches the final layout (no shift); empty, error and success states are designed.
- [ ] Keyboard: tab order is logical, focus ring is visible (2 px accent + 2 px offset), Esc closes the top layer.
- [ ] axe-core shows 0 serious or critical issues.
- [ ] Copy follows 5.8; no truncation without a tooltip; numbers are tabular.
- [ ] Motion is smooth and respects reduced motion.
- [ ] Looks deliberate and calm. If a screen feels busy, remove things before adding.

---

## 6. Data model (PostgreSQL)

**Conventions:**
- Every table has: `id uuid pk (uuid v7)`, `created_at`, `updated_at`, `created_by` (user id, nullable), `updated_by`.
- Tenant tables also have `company_id` with RLS (Section 4.3).
- Soft-archival uses `archived_at` / `withdrawn_at`, never DELETE, except a company purge and the explicit "permanently delete record created by mistake" action.
- Columns marked 🔒 are encrypted (Section 4.5); 🔎 means a blind index column also exists.
- Money is stored as `numeric(12,2)` with currency `GBP` by default.
- Enums are Postgres enums or check constraints, named as listed.
- Keep `docs/data-model.md` generated from models.

### 6.1 Platform and identity
- `companies`:
  - Identity: name, trading_name, slug (unique, for careers URL), registered_number (Companies House), type_of_organisation (legal structure enum, see 8.15), trading_period (enum), sector (SIC section enum), size_band.
  - Contact and locale: contact_email, contact_phone, website, logo_file_id, country (default GB), region (`uk`; `us`/`au` reserved), bank_holiday_region (`england-and-wales` | `scotland` | `northern-ireland`), timezone (default Europe/London), default_currency, week_starts_on (1 = Monday).
  - Leave: leave_year_start_month_day ("01-01"), allow_negative_leave_balance.
  - Security: mfa_policy (`optional` | `admins` | `all`).
  - Sponsor history: changed_name_last_5_years (bool), previous_company_name, penalty_illegal_working_last_3_years (bool), penalty_illegal_working_status.
  - Account: status (`active` | `suspended` | `pending_deletion` | `deleted`), plan (`free` | `annual` | `ten_year`), subscription_status, subscription_started_at, subscription_ends_at, cooling_off_ends_at, stripe_customer_id, stripe_subscription_id, setup_checklist_dismissed_at.
- `users`:
  - email (unique, citext), first_name, last_name, password_hash, email_verified_at, is_active.
  - MFA: mfa_enabled, mfa_secret 🔒, recovery_codes_hash[].
  - requires_password_change, last_login_at, failed_login_count, locked_until, theme_pref.
- `memberships`: user_id, company_id, role (enum of 6 roles), status (`active` | `suspended`), employee_id (link to HR record, unique per company). A user can belong to several companies; there is one active company per session.
- `platform_admins`: user_id, level (`support` | `owner`), mfa required.
- `sessions`: token_hash, user_id, company_id, ip, user_agent, created_at, last_seen_at, expires_at, revoked_at, mfa_passed_at, step_up_at.
- `invitations`: company_id, email, role, token_hash, expires_at, accepted_at, invited_by.
- `email_tokens`: user_id, purpose (`verify` | `reset` | `deletion_code` | `login_alert`), token_hash, expires_at, used_at.
- `terms_versions` (version, published_at, url) and `terms_acceptances` (user_id, version, accepted_at, ip).
- `audit_events` (append-only):
  - Context: company_id (nullable for platform events), actor_user_id, actor_type (`user` | `platform_admin` | `system`).
  - What happened: action (e.g. `employee.rtw.recorded`), entity_type, entity_id, summary, before jsonb, after jsonb (masked), reason.
  - Request: ip, user_agent, request_id, impersonation_session_id, created_at.
- `files`: company_id, storage_key, original_name, mime, size, sha256, scan_status (`pending` | `clean` | `infected` | `error`), scanned_at, owner_type, owner_id, category, uploaded_by.

### 6.2 Company settings and reference data
- `locations`: name, postcode, address_line1..3, city, county, country, is_default.
- `departments`: name, archived_at.
- `designations`: department_id, title, soc_code (optional link to SOC finder), archived_at.
- `key_persons`: role (`authorising_officer` | `key_contact` | `level1_user` | `level2_user`), first_name, last_name, designation, phone, email, proof_of_id_file_id, same_as_authorising_officer (bool), is_settled_or_british (Y/N question shown in the form).
- `company_compliance_documents`: doc_type (18 types, 8.15), file_id, expires_on, notes.
- `working_pattern`: per weekday (mon–sun) working (bool) and hours (numeric); bank_holidays_non_working (bool).
- `trading_hours`: per weekday open (bool), opens_at, closes_at.
- `company_bank_accounts`: label, bank_name, account_holder, sort_code 🔒, account_number 🔒, is_primary.
- `tax_codes`: code, reference, deduction_percentage.
- `payment_types`: name, min_hourly_rate.
- `pay_bands`: name, min_annual, max_annual, currency.
- `pay_schedules`: name, frequency (`weekly` | `fortnightly` | `four_weekly` | `monthly`), pay_day rule.
- `bank_holidays` (global, not tenant): region, date, title, source, fetched_at. Loaded from `https://www.gov.uk/bank-holidays.json`.
- `holiday_types`: name, colour.
- `company_holidays`: name, start_date, end_date, holiday_type_id, description, deduct_from_annual_leave (bool).
- `organogram_levels`: name, rank (default seed: "Director").

### 6.3 Employees
- `employees`:
  - Identity and contact: employee_number (unique per company, case- and space-insensitive), first_name, last_name, email, phone, alt_phone, date_of_birth, gender, marital_status, nationality (ISO country / demonym list), photo_file_id.
  - Lifecycle: hire_date, status (`active` | `on_leave` | `leaver` | `archived`), leave_date, opted_out_48h_week (bool).
  - Sensitive: ni_number 🔒🔎, passport_number 🔒, passport_country, passport_expiry.
- `employee_addresses`: postcode, line1, line2, line3, city_county, country, is_current.
- `emergency_contacts`: name, relationship (enum), phone, email, address, details.
- `employee_bank_details`: account_holder, bank_name, sort_code 🔒, account_number 🔒 (one current, history kept).
- `employee_assignments` (effective-dated, never overwritten):
  - Role: department_id, designation_id, location_id.
  - Reporting: reporting_authority_employee_id (line manager), leave_sanctioning_employee_id, organogram_level_id.
  - Working terms: employment_type (`full_time` | `part_time` | `fixed_term` | `zero_hours` | `casual` | `apprentice` | `agency`), custom_working_days (jsonb or null), hours_per_day (nullable).
  - Dates: effective_from, ended_at.
- `employee_responsibilities`: text, sort.
- `employee_compensation` (history):
  - amount, frequency (`annual` | `monthly` | `hourly`), contracted_hours_per_week.
  - tax_code_id, payment_type_id, pay_band_id, pay_schedule_id.
  - effective_from. Current = latest with effective_from ≤ today.
- `employee_previous_employment` (one row): job_title, started_on, left_on, total_experience_years, description.
- `employee_education`: qualification, subject, institution, awarding_body, year, percentage, grade.
- `employee_training_records`: title, start, end, description.
- `employee_memberships`: licence_title, licence_number, start, end.
- `employee_documents`: file_id, category (`employment_contract` | `letter` | `hr_record` | `id_document` | `rtw_evidence` | `certificate` | `payslip` | `other`), notes.

### 6.4 Right to Work and sponsor compliance
- `rtw_checks`:
  - Subject: subject_type (`employee` | `candidate`), subject_id.
  - Check: check_type (`online_share_code` | `idsp_digital` | `manual_list_a` | `manual_list_b`), share_code 🔒, idsp_provider, list_b_group (`group1` | `group2`), permission_expires (bool), permission_expires_on, follow_up_due_on (computed).
  - Outcome: check_date, checked_by_user_id, outcome (`pending` | `verified` | `failed`), evidence_file_id.
  - Lifecycle: superseded_at, superseded_by, corrected_from_id, correction_reason.
  - Derived status (computed in a view): `verified` | `expiring` (≤60 days to follow-up) | `expired` | `failed` | `pending` | `evidence_missing` | `not_recorded`.
- `sponsor_documents`:
  - Type and identity: employee_id, doc_type (`visa` | `passport` | `dbs` | `euss` | `national_id` | `other`), reference_number 🔒, issuing_country.
  - Visa details: visa_route (enum, 8.5), cos_number 🔒, soc_code, sponsored_salary.
  - Dates: issue_date, expiry_date, review_date.
  - Evidence and lifecycle: evidence_file_id, remarks, version, superseded_by, withdrawn_at, withdraw_reason.
- `reminders`:
  - sponsor_document_id, threshold_days (90 | 60 | 30), due_on.
  - status (`scheduled` | `due` | `sent` | `snoozed` | `cancelled`), message_draft (AI-drafted text), sent_at, sent_by_user_id, snoozed_until.
- `change_of_circumstances`:
  - The change: employee_id, change_type (enum, 8.5), change_date, deadline_date (computed: 10 working days, or 20 for organisation changes).
  - Snapshot: employment_type, job_title, nationality, contact_number, address, remarks.
  - Acknowledgements and documents: ack_inform_hr (bool), ack_home_office_interview (bool), documents_snapshot (jsonb of current doc ids).
  - Reporting: reported_at, reported_by_user_id, reported_reference.
- `org_changes` (organisation-level reportable changes, 20 working days): change_type, change_date, deadline_date, reported_at.

### 6.5 Leave
- `leave_types`:
  - name, is_paid, counts_toward_statutory (bool), days_per_year (nullable), carry_over_limit_days.
  - accrual_method (`front_loaded` | `monthly`), requires_approval, colour, rule_text, archived_at.
  - Seed the 12 defaults from 8.6.
- `leave_ledger` (the source of truth for balances): employee_id, leave_type_id, leave_year_start, entry_type (`grant` | `accrual` | `carry_over` | `taken` | `adjustment` | `deduct` | `set` | `year_end_expiry`), days (signed), reason, leave_request_id, created_by.
- `leave_balances` (view): sum of the ledger per employee, type and year.
- `leave_requests`: employee_id, leave_type_id, start_date, end_date, half_day_start, half_day_end, working_days (computed against the working pattern, personal days, bank holidays and company closures), note, status (`pending` | `approved` | `rejected` | `cancelled`), decided_by, decided_at, decision_note.
- `leave_year_end_runs`: from_year, to_year, run_by, overrides jsonb, committed_at.

### 6.6 Attendance, rota and work log
- `attendance_records`: employee_id, date (unique per employee), status (`present` | `absent` | `late` | `half_day` | `on_leave` | `sick`), clock_in, clock_out, unpaid_break_minutes, hours (computed), note, source (`manual` | `import` | `grid` | `clock` | `leave_sync`), geo (optional, opt-in).
- `attendance_imports`: file_id, from, to, rows_total, rows_valid, errors jsonb, status (`previewed` | `committed`).
- `timesheet_approvals`: employee_id, period_start, period_end, approved_by, approved_at.
- `shift_types`: name, description, starts_at, ends_at, break_start, break_end, colour.
- `late_policies`: department_id, designation_id, shift_type_id, grace_minutes, allowed_late_days_per_month, deduction_type (`none` | `fixed` | `percentage_of_day`), deduction_value.
- `day_off_patterns`: department_id, designation_id, shift_type_id, weekdays_off (int[]), works_public_holidays (bool).
- `rota_weeks`: week_start, status (`draft` | `published`), published_at, published_by.
- `scheduled_shifts`: rota_week_id, employee_id, date, starts_at, ends_at, unpaid_break_minutes, shift_type_id, note.
- `work_log_entries`: employee_id, date, from_time, to_time, responsibility_id (nullable), description, removed_at, removed_by, corrected_from (jsonb).

### 6.7 Documents, policies and reports
- `company_documents`: file_id, category (10 values, 8.10), next_review_date, title, archived_at.
- `letter_drafts`: letter_type, tone, key_points jsonb, output_text, created_by (no employee identifiers stored).
- `policy_documents`:
  - title, category (23 values, 8.10), file_id, confirmation_mode (`accept` | `sign`).
  - audience_type (`everyone` | `departments` | `locations` | `named` | `visa_holders`), audience_ids uuid[].
  - accept_within_days, auto_send_new_starters, status (`draft` | `sent` | `archived`), sent_at, version.
- `policy_acceptances`: policy_document_id, employee_id, due_on, status (`pending` | `accepted` | `signed` | `overdue`), accepted_at, typed_signature, ip, user_agent.

### 6.8 Recruitment
- `requisitions`: job_title, department_id, headcount, grade, budget_from, budget_to, budget_per (`year` | `month` | `hour`), justification, status (`draft` | `open` | `on_hold` | `filled` | `cancelled`), approved_by, approved_at.
- `postings`:
  - Basics: requisition_id, title, slug, visibility (`internal` | `external`), location_id, job_code, soc_code, vacancies.
  - Dates and contact: posted_on, closes_on, contact_email, contact_phone.
  - Pay and hours: salary_from, salary_to, salary_per, weekly_hours.
  - Content and status: description (plain text), visa_sponsorship (`not_stated` | `available` | `considered` | `not_available`), status (`draft` | `open` | `closed`).
- `candidates`: first_name, last_name, email, phone, source, cv_file_id, rtw_status (derived), archived_at.
- `applications`: candidate_id, posting_id, stage (`applied` | `shortlisted` | `interview` | `offer_letter` | `offer_accepted` | `hired` | `rejected` | `withdrawn`), stage_history jsonb[], cover_note, applied_via (`admin` | `careers_page`).
- `interviews` (new): application_id, scheduled_at, duration_minutes, mode (`in_person` | `video` | `phone`), location_or_link, interviewer_employee_ids uuid[], outcome (`pending` | `passed` | `failed` | `no_show`), notes.
- `offers`: application_id, role_title, salary, salary_per, start_date, status (`draft` | `sent` | `accepted` | `declined` | `withdrawn`), decided_at.

### 6.9 Learning
- `courses` (global content, managed in super-admin): slug, title, summary, duration_minutes, audience (`all_staff` | `managers`), sections jsonb (ordered; text, key points, check questions), quiz jsonb, pass_mark, source_title, source_publisher, source_url, source_updated_on, content_reviewed_on, licence_note, published (bool), version.
- `course_assignments`: course_id, employee_id, due_on, status (`not_started` | `in_progress` | `completed` | `overdue`), progress jsonb, quiz_score, completed_at, assigned_by.
- `certificates`: assignment_id, reference (random 10-char, unique, public), issued_on, holder_name_snapshot, course_title_snapshot.

### 6.10 SOC Sponsorship Job Checker (rules data is global, results are tenant)
- `rules_versions`: name, source_urls jsonb, effective_from, published_at, published_by, status (`draft` | `live` | `retired`), diff_summary.
- `soc_unit_groups`: code (4-digit SOC 2020), title, description, tasks text[], entry_requirements, typical_titles text[], rqf_level (6 | `3-5` | below), embedding vector(384).
- `soc_index_entries`: index_title (ONS coding index, about 30k), qualifier_add, qualifier_ind, soc_code, embedding vector(384), trigram index on index_title.
- `going_rates`: rules_version_id, soc_code, table (`1` | `1a` | `2` | `2a` | `2aa` | `2b` | `3` | `3a`), annual_rate, hourly_rate, rate_90, rate_80, rate_70, phd_points_eligible (bool), basis_hours (37.5, or 40 for doctors), notes.
- `pay_scale_rates` (Tables 4/5): rules_version_id, soc_code, administration (England / Scotland / Wales / NI), band_or_role, annual_rate.
- `ineligible_codes` (Table 6): rules_version_id, soc_code, reason.
- `shortage_list_entries`: rules_version_id, list (`TSL` | `ISL`), soc_code, condition_text, nations text[], removal_date, dependants_allowed (bool).
- `salary_rules`: rules_version_id, option (`A`..`K`), general_threshold, going_rate_pct, criteria_key (e.g. `new_entrant`, `phd`, `stem_phd`, `isl`, `health_education`), applies_to (`new` | `transitional_pre_2024` | `transitional_pre_jul_2025` | `health_care`).
- `soc_checks` (tenant): created_by, posting_id or candidate_id (nullable), input_title, input_description, hours, offered_salary, salary_per, work_nation, applicant_situation jsonb, cos_assignment_date, rules_version_id, result jsonb (ranked codes, chosen code, eligibility, salary table, pass/fail, explanations), resume_file_id (nullable), resume_match jsonb, confirmed_code, confirmed_by, confirmed_at, report_file_id.

### 6.11 Billing, notifications and AI
- `subscriptions`: company_id, stripe_subscription_id or stripe_payment_intent_id (10-year), plan, status, current_period_start, current_period_end, cancel_at, refunded_at.
- `stripe_events`: event_id (unique), type, processed_at, payload_hash.
- `deletion_requests`: company_id, requested_by, code_hash, confirmed_at, scheduled_for (+7 days), withdrawn_at, export_requested (bool), export_file_id, completed_at.
- `data_exports`: company_id, requested_by, status, file_id, expires_at.
- `notifications`: user_id, company_id, kind, title, body, link, read_at.
- `ai_interactions` (metadata only, 30-day retention): user_id, company_id, feature (`ask` | `letter` | `reminder` | `soc_match` | `resume_match`), tokens_in, tokens_out, model, latency_ms, refused (bool), created_at. **No prompt text or answers are stored.**

### 6.12 Public data (global, not tenant)
- `contact_messages`: name, company, email, topic (7 values, 8.20), message, ip_hash, created_at, handled_at.
- `register_publications`: published_on, source_url, row_count, sha256, fetched_at, status.
- `register_sponsors`: stable_id (random slug), organisation_name, normalised_name, town, county, region_itl1, lat, lon, place_precision (`town` | `county` | `region` | `none`), companies_house_number, sic_section, first_seen_on, last_seen_on, current (bool).
- `register_entries`: publication_id, sponsor_id, type_rating (e.g. "Worker (A rating)"), route (Skilled Worker, Global Business Mobility, …).
- `register_changes`: publication_id, sponsor_id, change (`added` | `removed` | `returned` | `rating_changed` | `route_added` | `route_removed` | `renamed`), detail jsonb.
- `register_possible_matches`: added_sponsor_id, removed_sponsor_id, similarity, reason.
- `register_reports` ("Report a problem with an entry"): sponsor_id, message, email, status.

---

## 7. Roles and permissions (exact matrix — implement as data, test as a matrix)

Store the permissions in `api/app/core/rbac_matrix.py` as a constant, with one source of truth. The UI reads `GET /auth/me.permissions`.

### 7.1 Full permission list (Company Admin has all 110 + the new ones marked ★)
```
attendance.record.read | attendance.record.read_own | attendance.record.write | attendance.record.write_own
attendance.timesheet.approve_reports
company.department.read | company.department.write | company.location.read | company.location.write
company.overview.read | company.profile.read | company.profile.write
document.file.read | document.file.read_own | document.file.write | document.file.write_own | document.report.generate
employee.change_of_circumstances.read | employee.change_of_circumstances.write
employee.compensation.read | employee.compensation.write
employee.org_assignment.read | employee.org_assignment.write
employee.profile.delete | employee.profile.read | employee.profile.read_own | employee.profile.read_reports
employee.profile.write | employee.profile.write_own
employee.rtw.correct | employee.rtw.read | employee.rtw.read_own | employee.rtw.write
employee.sensitive_data.read | employee.sensitive_data.read_own | employee.sensitive_data.write
holiday.calendar.read | holiday.calendar.write | holiday.type.read | holiday.type.write
learning.assignment.complete_own | learning.assignment.read | learning.assignment.read_own
learning.assignment.read_reports | learning.assignment.write
learning.certificate.read | learning.certificate.read_own | learning.course.read
leave.accrual.write | leave.balance.read | leave.balance.read_own | leave.balance.read_reports
leave.config.read | leave.config.write
leave.request.approve | leave.request.approve_reports | leave.request.create | leave.request.create_own
leave.request.read | leave.request.read_own | leave.type.read | leave.type.write
organogram.level.read | organogram.level.write
policy.acceptance.read_own | policy.acceptance.write_own | policy.document.read | policy.document.write
rbac.role.assign | rbac.user.invite | rbac.user.read
recruitment.application.read | recruitment.application.write
recruitment.candidate.convert | recruitment.candidate.read | recruitment.candidate.write
recruitment.interview.read | recruitment.interview.write | recruitment.offer.read | recruitment.offer.write
recruitment.pipeline_stage.write | recruitment.posting.read | recruitment.posting.write
recruitment.requisition.approve | recruitment.requisition.read | recruitment.requisition.write
rota.day_off.read | rota.day_off.write | rota.duty_roster.read | rota.duty_roster.write | rota.duty_roster.write_reports
rota.late_policy.read | rota.late_policy.write | rota.scheduled_shift.read_own | rota.shift.read | rota.shift.write
settings.designation.read | settings.designation.write | settings.pay_band.read | settings.pay_band.write
settings.payment_type.read | settings.payment_type.write | settings.pay_schedule.read | settings.pay_schedule.write
settings.tax_code.read | settings.tax_code.write
work_log.entry.correct | work_log.entry.read | work_log.entry.read_own | work_log.entry.write_own
★ compliance.overview.read | ★ compliance.reminder.send | ★ compliance.audit.read | ★ compliance.audit.export
★ soc.check.run | ★ soc.check.read | ★ ai.ask.use | ★ ai.letter.draft
★ billing.manage | ★ company.delete | ★ company.export
```

### 7.2 Role grants
- **Company Admin:** everything above.
- **HR Admin:**
  - Has: every `.read` and `.write` above (non-own, non-reports); `employee.profile.delete`; `employee.sensitive_data.read/write`; `employee.rtw.read/write`; `employee.change_of_circumstances.*`; `employee.compensation.*`; `employee.org_assignment.*`; `leave.request.approve`; `leave.accrual.write`; `recruitment.*` including `requisition.approve` and `candidate.convert`; `rbac.user.invite` (**cannot invite or assign Company Admin**); `rbac.user.read`; `document.report.generate`; `work_log.entry.read`; `learning.assignment.complete_own`; `policy.acceptance.*_own`; `rota.scheduled_shift.read_own`; ★ `compliance.overview.read`, `compliance.reminder.send`, `compliance.audit.read`, `soc.check.run/read`, `ai.ask.use`, `ai.letter.draft`.
  - Does **not** have: `company.profile.write`, `rbac.role.assign`, `employee.rtw.correct`, `work_log.entry.correct`, `attendance.timesheet.approve_reports`, `billing.manage`, `company.delete`, `company.export`.
- **People Manager:** attendance.record.read, attendance.timesheet.approve_reports, company.department.read, company.location.read, company.overview.read, employee.profile.read_reports, holiday.calendar.read, learning.assignment.complete_own, learning.assignment.read_own, learning.assignment.read_reports, learning.certificate.read_own, learning.course.read, leave.balance.read_reports, leave.request.approve_reports, organogram.level.read, policy.acceptance.read_own, policy.acceptance.write_own, recruitment.application.read, recruitment.candidate.read, recruitment.interview.read, recruitment.interview.write, recruitment.posting.read, recruitment.requisition.read, recruitment.requisition.write, rota.day_off.read, rota.duty_roster.read, rota.duty_roster.write_reports, rota.late_policy.read, rota.scheduled_shift.read_own, rota.shift.read, settings.designation.read, ★ ai.ask.use.
- **Recruiter:** company.department.read, company.location.read, company.overview.read, recruitment.* except `requisition.approve`, settings.designation.read, ★ soc.check.run, ★ soc.check.read.
- **Employee:** attendance.record.read_own, company.overview.read, document.file.read_own, document.file.write_own, employee.profile.read_own, employee.profile.write_own (contact, address, emergency contacts only), employee.rtw.read_own, employee.sensitive_data.read_own, holiday.calendar.read, learning.assignment.complete_own, learning.assignment.read_own, learning.certificate.read_own, learning.course.read, leave.balance.read_own, leave.request.create_own, leave.request.read_own, leave.type.read, policy.acceptance.read_own, policy.acceptance.write_own, rota.scheduled_shift.read_own, work_log.entry.read_own, work_log.entry.write_own, ★ ai.ask.use (own data only), plus `attendance.record.write_own` **only for clock in/out**.
- **Read-only Auditor:** every non-own `.read` in company, employee (including compensation, CoC, rtw, org_assignment), holiday, learning, leave config/request/type, organogram, policy document, rbac user, recruitment, rota, settings and work log, plus ★ compliance.overview.read, compliance.audit.read, compliance.audit.export, soc.check.read. **No `.write`, no sensitive reveal, no AI.**
- **Platform Admin (super-admin):** a separate `/admin` API with its own permission set (`platform.companies.read/write`, `platform.billing.refund`, `platform.impersonate`, `platform.rules.publish`, `platform.content.write`, `platform.jobs.run`, `platform.audit.read`). Never mixed with tenant roles.

### 7.3 Rules
- A Company must always have at least one active Company Admin. Block demoting, suspending or removing the last one.
- Only a Company Admin can assign or remove the Company Admin role.
- People with `_reports` scope see their direct and indirect reports by Reporting Authority. Leave approvals use the Leave Sanctioning Authority relationship.
- Self-approval is forbidden: no one approves their own leave or timesheet.

---

## 8. Module specifications (behaviour, screens, reference data)

Each module lists **screens**, **behaviour rules** and **reference data**. The build order is in Section 9.

### 8.1 Auth and onboarding
- **`/login`:**
  - region switch (UK active; USA and AU disabled with "coming soon");
  - email, password (show/hide), "Forgot password?", "Create your company account".
  - After 3 failed attempts a Turnstile challenge appears.
  - If MFA is required or enabled, go to `/login/mfa` (6-digit code, or "use a recovery code").
- **`/setup`** (two-step wizard with Stepper and a "Your choices so far" disclosure):
  1. **Company:** company name, bank holiday region (England & Wales / Scotland / Northern Ireland).
  2. **Your account:** first name, last name, work email, password with a strength meter, terms acceptance checkbox, Turnstile.
  - Creates the Company + first **Company Admin** on the **free plan**, then sends the verification email.
  - Screen: "Check your inbox", with resend after 60 s.
- **`/verify-email?token=`** marks the email verified, signs the user in and goes to the dashboard.
- **`/forgot-password` and `/reset-password?token=`**: neutral responses (no account enumeration).
- **`/accept-invite?token=`**: set name and password, accept terms, MFA setup if the policy requires it.
- **Terms gate:** if `terms.acceptance_required`, show a full-screen sheet before anything else.
- **MFA enrolment** (when the policy requires it): QR code with a manual key, a confirm code, then show 10 recovery codes once ("Download" / "I've saved them").
- **Free plan banner:** "You're on the free plan — subscribe to add employees" with a Subscribe button. It is not dismissable on write screens.

### 8.2 Dashboard (`/dashboard`)
- **Header:**
  - greeting by time of day ("Good morning, {first}");
  - a one-line status ("Nothing needs your attention today" / "1 item is overdue and 2 leave requests are waiting");
  - quick actions: Add employee, Add candidate, Request leave, Upload document.
- **KPI cards:** Employees (active · on leave), Present today (x of y), On leave (currently away), Documents on file (available and scanned).
- **Get set up checklist** (progress bar, dismissable, hidden once complete or after data exists):
  - add Company details;
  - departments & locations;
  - first employee;
  - first Right to Work check;
  - key personnel;
  - upload sponsor licence.
- **Cards:**
  - Needs attention (top 5 with action buttons);
  - Right to Work coverage % with status counts;
  - Attendance today (Present / Absent / Late / Half day);
  - Who is off;
  - Approvals;
  - Employee distribution (headcount by department, with an "Unassigned" bucket);
  - Ask the assistant (inline input + 3 suggestion chips);
  - My leave balance;
  - Employees (recent, with RTW status);
  - Recruitment (latest candidates).
- Each card links to its module and respects permissions: hide cards the user can't read.

### 8.3 Employees
- **List `/employees`:**
  - quick pills: All · Active · Needs Right to Work action · On leave · Leavers;
  - search by name or employee number;
  - filters: department, status, RTW status (Needs attention / Verified / Expiring / Evidence missing / Expired or failed / Pending / Not recorded), plus a "Show archived" toggle;
  - summary line ("12 employees · 10 active · 1 on leave · all Right to Work checks current");
  - columns: Employee (avatar, name, number), Department, Designation, Right to Work, Status;
  - deep links `?rtw=Verified|Expiring|EvidenceMissing|Expired|Pending|NotRecorded`;
  - keyboard J/K/Enter, N = new, / = search.
- **Archived list `/employees/archived`.**
- **Create `/employees/new`** (essentials only): first name*, last name*, email*, contact number, employee number* (unique ignoring case and spaces), hire date* (no more than 12 months ahead), status. Add a side note linking the New Starter Checklist (original template).
- **Profile `/employees/{id}`.**
  - **Header:** avatar with "Add photo", name, status chip, number, "Joined {date} · {relative}", RTW pill with "Resolve Right to Work", alert banner if there is no RTW check.
  - **Tabs:**
    1. **Overview:**
       - summary cards (Right to Work, sponsor documents count, Employment, Leave balance, Documents);
       - "Access & status": lifecycle buttons Set to On leave / Leaver / Archived with **inline confirm** and an optional leave date;
       - "Opted out of the 48-hour week" toggle (needs the signed agreement uploaded; the rota stops warning);
       - collapsed "Advanced: permanently delete this record" (Company/HR Admin; requires typing the name; only allowed when there are no RTW checks, sponsor documents or audit-relevant history, otherwise it explains to archive instead).
    2. **Personal:**
       - personal details (first, last, email, contact, alternative, DOB, gender [Not specified / Male / Female / Non-binary / Prefer not to say / Other], marital status [Not specified / Single / Married / Civil partnership / Separated / Divorced / Widowed / Prefer not to say], nationality);
       - correspondence address (with postcodes.io lookup);
       - emergency contacts (relationship: Spouse / Civil partner / Partner / Parent / Child / Sibling / Guardian / Other relative / Friend / Other);
       - National Insurance & passport (masked, reveal with step-up);
       - bank details (masked, reveal with step-up).
    3. **Employment:**
       - hire date with "Edit hire date" (new date + reason, audited; no record may start before it);
       - **Current role** (effective-dated assignment) with **history** and a "Change role" sheet: department, designation (filtered), location, Reporting Authority, hierarchy level, Leave Sanctioning Authority, employment type, "Works different days from the company" plus day picker, hours a day, effective from*;
       - **Salary** (hidden until "Show salary", which requires `employee.compensation.read`), with history and an "Add salary record" sheet: amount, frequency, contracted hours a week (with a National Minimum Wage check that warns if hourly is below the rate for the age band), tax code, payment type, pay band, pay schedule, effective from (≥ hire date);
       - key responsibilities;
       - previous employment;
       - education;
       - training;
       - certified memberships.
       - **Important:** forms that are always visible must not auto-submit. Every save is an explicit button.
    4. **Leave:** balances per type with rule text; admin actions Grant (days, or "use standard entitlement"), Deduct, Set balance (each needs a reason and writes to the ledger); requests list; new request on behalf of the employee.
    5. **Attendance:** history table with a month filter; link to the workspace.
    6. **Documents:** sub-tabs All / Payslips; upload with category; scan status; download via short-lived link.
    7. **Right to Work:** see 8.4.
    8. **Sponsor Compliance:** see 8.5.
    9. **Learning** (new tab): assignments and certificates.
    10. **Activity** (new tab, for `compliance.audit.read`): this person's audit trail.
- **Print / PDF:** "Print record" produces a full employee record PDF (sensitive fields masked) for inspections.

### 8.4 Right to Work
- **Current check card + history** (superseded checks are kept as evidence). Users with `employee.rtw.correct` can correct a check, which needs a reason and creates a new linked version.
- **Record a check** (sheet, with a "Check on GOV.UK" link at the top). The check type decides which fields appear:

| Check type | Fields | Follow-up |
|---|---|---|
| Home Office online check (share code) | share code* (9 chars, A–Z0–9, stored encrypted), "Does permission run out?" No (settled/indefinite) / Yes (+ expiry date*) | Yes if it expires; due on the expiry date |
| Digital identity check (certified IDSP) | certified provider*; only for British/Irish passport or Irish passport card | None |
| Manual check — List A | — | None |
| Manual check — List B | Group 1 (document shows end date) / Group 2 (Positive Verification Notice), permission expires on* | Due by that date |

- **Common fields:** date of check*, checked by (user), outcome (Pending / Verified / Failed), evidence document (pick from uploaded files; the upload panel below auto-selects the new file).
- **Derived statuses:**
  - **Expiring** = follow-up due within 60 days;
  - **Expired** = follow-up date passed;
  - **Evidence missing** = verified without evidence;
  - **Not recorded** = no check.
- **Evidence sheet PDF** per check: type, date, outcome, expiry, checker and evidence file name, dated and printable.
- **Candidates** have the same check, without the "checked by" and date fields made mandatory. The current check drives the conversion gate.

### 8.5 Sponsor compliance
- **Hub `/sponsor-compliance`:**
  - header with links "Check right to work on GOV.UK" and "Compliance Reminders";
  - **Needs attention queue** (ordered by urgency; each row says the action and where to take it: expired RTW, expiring RTW, no check on file, documents expiring, CoC past deadline);
  - **RTW coverage** (x of y hold a valid check, status counts linking to the filtered employee list);
  - **Inspection readiness** (x of 5): company profile complete; key personnel recorded (AO, Key Contact, Level 1 User); company compliance documents uploaded; every current employee has an RTW check; every reportable change reported on time (or "Not applicable");
  - **Expiring in the next 90 days** (Overdue / Next 30 / 31–60 / 61–90 columns; filter by document type);
  - **Activity** from the audit log (filters: All, Right to Work, Employees, Attendance, Documents, Changes; Export CSV);
  - **Compliance tools** cards: Company Profile, Sponsored employees, Change of Circumstances, Key Personnel, Company compliance documents, Sponsor Management Dossier.
- **Employee Sponsor Compliance tab:**
  - "Sponsor compliance record" PDF;
  - 6 document types (Visa, Passport, DBS certificate, EUSS status, National ID, Other), each with Add / Update (new version supersedes) / Plan renewal / Withdraw (reason required; stays in audit trail);
  - change-of-circumstances log with "Log a change".
- **Visa fields:** eVisa/visa reference, issuing country, **visa route*** (Skilled Worker / Health and Care Worker / Global Business Mobility / Scale-up / Temporary Worker / Graduate / Student / EUSS settled / EUSS pre-settled / Family / Other), CoS number, SOC code (with "Find code" opening the SOC checker), sponsored salary, issue/expiry/review dates, evidence, remarks.
  - A sponsored route adds the employee to **Sponsored employees** (Skilled Worker, Health and Care Worker, Global Business Mobility, Scale-up, Temporary Worker; EUSS excluded).
- **Change of circumstances** ("Log a change"):
  - type* (Didn't start work / Unauthorised absence of more than 10 working days / Left, or sponsorship stopped (including dismissal or resignation) / Salary reduced / Change of job or SOC code / Change of main work location / Change in working hours / Unpaid or reduced-pay absence over 4 weeks in a year / Other reportable change);
  - date of change (the deadline is counted from it: **10 working days**, excluding weekends and bank holidays for the company's region);
  - snapshot fields (employment type, job title, nationality, contact number, address, remarks/restriction to work);
  - two acknowledgement checkboxes (employee told to inform HR promptly; employee told to cooperate with a Home Office interview);
  - tick the current documents that apply.
  - Each entry shows "N working days left", "Past deadline", or "Reported by X on date" with a **Mark as reported** sheet (date, SMS reference).
- **Organisation changes** (20 working days): log on the hub (change of address, ownership, key personnel, etc.).
- **`/sponsor-compliance/change-of-circumstances`:** company-wide log; filters All / Still to report / Past the deadline; search.
- **`/sponsor-compliance/migrant-employees`:** sponsored employees table (route, CoS, SOC, visa expiry, RTW status).
- **`/sponsor-compliance/dossier`:** curated official GOV.UK links grouped as "Holding a licence", "Right to Work" and "SMS manuals", plus a downloadable RTW checklist (our own original PDF). The links are editable in super-admin.
- **Reminders `/sponsor-compliance/reminders`:**
  - **Due now** (documents past a 90/60/30-day threshold without a reminder) with "Review & send";
  - **Document register** tabs Visa / Passport / DBS / EUSS / Other with threshold chips (✓ sent, due, scheduled) that open the drawer;
  - **History** of sent reminders, recording **who** sent it and **when** (an improvement on the reference).
  - **Review drawer:** employee, document, expiry, status "Drafted, not sent", and an editable message (AI-drafted, no identifiers sent to AI; see 8.12). Actions: Not now (snooze 7 days) / Send reminder.
  - Sending posts the message to the employee's My Documents/notifications and emails a short nudge that **does not name the document**.
- A **daily job** creates or advances reminders, recomputes RTW statuses and CoC deadlines, and creates notifications for admins.

### 8.6 Leave and holidays
- **Default leave types (seed):**

| Type | Paid | Statutory | Default days | Rule text (write original, from GOV.UK) |
|---|---|---|---|---|
| Annual Leave | Yes | Yes | 28 (incl. bank holidays), carry up to 5 | 5.6 weeks, pro-rated |
| Sick Leave | Yes | No | — | SSP from day one (verify current rule) |
| Maternity Leave | Yes | No | — | up to 52 weeks; SMP up to 39 if eligible |
| Paternity Leave | Yes | No | — | up to 2 weeks within 52 weeks |
| Adoption Leave | Yes | No | — | up to 52 weeks |
| Shared Parental Leave | Yes | No | — | up to 50 weeks, up to 3 blocks |
| Neonatal Care Leave | Yes | No | — | up to 12 weeks |
| Parental Bereavement Leave | Yes | No | — | up to 2 weeks within 56 weeks |
| Parental Leave | No | No | — | unpaid |
| Carer's Leave | No | No | — | 1 week per 12 months |
| Time Off for Dependants | No | No | — | reasonable time, unpaid |
| Unpaid Leave | No | No | — | — |

  Verify every rule against GOV.UK when seeding; store the source URL and date checked.
- **Leave settings:** leave year start (MM-DD, hint 01-01 or 04-06), allow negative balances, leave types table (add/edit/archive: name, paid, counts toward statutory minimum, days a year, carry-over limit, colour).
- **Year end:** preview each person's carry-over up to the limit, allow per-person overrides (long sickness or family leave), commit. This writes ledger entries, and the run is audited.
- **Balances** come from the **ledger**:
  - pro-rated for starters and leavers;
  - part-time pro-rating by personal working days or hours;
  - bank holidays that fall on a person's working days are deducted where "bank holidays included".
- **Leave `/leave`** (SegmentedControl):
  - **Calendar:** month grid with department filter, colour by type, Today button;
  - **Requests:** awaiting decision, with approve/reject and a note; history; conflict warnings (same team overlap, rota shifts, below minimum staffing);
  - **Balances:** a table per employee per type, with days taken this year.
- **Approval:**
  - approving books leave (ledger "taken"), marks attendance as `on_leave` for those days and removes or flags clashing shifts;
  - rejecting leaves the balance untouched;
  - the employee is notified by email and in the app.
- **Holidays `/holiday-management`:**
  - company closure days (date range, one entry per shutdown), with an optional type, description and "Take these days from annual leave" toggle;
  - holiday types;
  - year navigation;
  - bank holidays shown read-only from GOV.UK for the region, refreshed weekly.
- **Working pattern** (Company → Time): per-day on/off and hours, plus a toggle for treating bank holidays as non-working.
- **My Leave:** balances, a request form (type, start, end, half days, note, live working-days count), history, and cancelling pending requests.
- **My Approvals:** requests from employees where I am the Leave Sanctioning Authority.

### 8.7 Attendance
- **Workspace `/attendance`:**
  - toolbar: Import, Export Excel, Export PDF, Absences this month, Record attendance;
  - KPIs for the selected day: Employees, Present, Absent, Late, Half day, On leave/Sick;
  - range: Day / Week / Month / Custom; filters for employee and status;
  - records table (employee, date, status, in, out, break, hours, note, source).
- **Record attendance sheet:** employee*, date, status (Present / Absent / Late / Half day / On leave / Sick), clock in*, clock out*, unpaid break (minutes), note. Saving for an existing employee and date updates that record.
- **Import:**
  - download a template (xlsx with a status dropdown, or CSV) with columns `employee_number, date (YYYY-MM-DD), status, clock_in, clock_out, note`;
  - upload, then a **preview** with per-row validation errors, then commit;
  - rows are matched on employee number.
- **Bulk entry grid:** employees × days with status pickers; existing records are editable in place; one submit.
- **Absences this month** report.
- **Late detection** uses the late policy for the employee's department, designation and shift.
- **Clock in/out (new, PWA):**
  - employees use My Shifts / Home to Clock in and Clock out, with an optional note;
  - optional geolocation only if the company enables it and the employee consents;
  - creates `attendance_records` with `source=clock`;
  - People Managers approve timesheets for their reports.
- Sickness entries are health data: restrict access and exclude them from AI.

### 8.8 Rota
- **`/rota`** week view:
  - toolbar: Shift types link, Print (A4 landscape PDF for a notice board), **Publish week**;
  - week navigation (Mon–Sun, today highlighted), "Find someone", Copy last week, ⋯ menu (Clear this whole week);
  - **Quick add** chips for each shift type (one click fills the selected cell);
  - **Draft** banner ("not visible to employees yet") until published; editing a published week puts it back to "changes not published";
  - rows: employee (avatar, name, number), with a ⋯ menu (Copy their last week / Clear their week);
  - day header ⋯ menu: Copy to the rest of Mon–Fri / Copy to every other day / Clear this day;
  - cell "+" opens the **Add shift** sheet: starts, finishes (live "8h paid"), unpaid break, employee (reassign), date, shift type (optional), note;
  - footer row: "On shift" hours per day;
  - "Not scheduled this week (n)" list.
- **Warnings:** clashes with approved leave or company holidays; more than 48 hours a week unless the employee has opted out; less than 11 hours rest between shifts.
- **Publishing** notifies affected employees (in-app + email digest). My Shifts shows published shifts only.
- **Settings `/rota/settings`** (tabs):
  - **Shift types:** name with suggestion chips (Morning / Afternoon / Evening / Night / Early / Late / Day / Weekend), description, in/out, break start/end;
  - **Late policy:** per department + designation + shift — grace minutes, allowed late days per month, deduction type/value;
  - **Day off patterns:** per department + designation + shift — weekdays off, works public holidays.
  - Late policy and day off need a department, designation and shift to exist; the empty state explains this and links to create them.

### 8.9 Work Log
- **My Work Log:** add a daily entry (date, from, to, responsibility from my key responsibilities or free text, what I did); edit my own entries the same day.
- **Admin `/work-log`:**
  - KPIs: entries in range, hours logged, employees;
  - search, employee filter, date range, show removed, show archived;
  - **Correct** (keeps the original in `corrected_from`) and **Remove** (soft), both audited with a reason.

### 8.10 Documents, policies and reports
- **Company documents `/documents`:**
  - upload with **category**: Policy or staff handbook / Health & safety / Companies House record / HMRC or payroll record / Insurance certificate / Premises or lease / Certificate or qualification / HR template or form / Training material / Other;
  - optional **next review date** (flagged when within 30 days);
  - file drag-drop (PDF/JPG/PNG/Word, ≤25 MB, scanned).
  - Per-person files are uploaded from the person's profile, and the page says so.
- **Draft with AI** (sheet):
  - letter type: Offer letter / Welcome or onboarding letter / Disciplinary letter / Formal written warning / Policy explainer / Employment reference / Termination letter;
  - tone: Formal / Neutral / Friendly;
  - key points (list input).
  - The output is an editable draft using placeholders such as `[Employee name]`. **No names or identifiers are sent to AI.**
  - Actions: copy, download .docx, save as company document.
- **Reports** (xlsx, generated fresh by a worker job, then a download link):
  - **Employee Directory:** number, name, department, status, hire date.
  - **Employee Detail:** adds designation, location, leave date, RTW status; no pay or sensitive IDs.
  - **Archived Employees.**
  - **Company Report:** identity, address, HR settings, departments, locations, key personnel, trading hours, compliance documents.
  - New: **Sponsor Workers Report**, **Leave Taken Report**, **Training Completion Report**.
- **Policies & Sign-offs `/policies`:**
  - list with an acceptance progress bar per document;
  - **New document** (3 steps: Details → Upload file → Recipients & send):
    - title*, category* (Employment contract / Job description / Offer letter / Contract change letter / Company policy (general) / Employee handbook / Code of conduct / IT, email and social media / Drugs and alcohol / Sickness and sick pay / Attendance and punctuality / Holiday and annual leave / Flexible and hybrid working / Family leave / Equality and diversity / Anti-harassment and bullying / Grievance / Disciplinary / Whistleblowing / Health and safety / Employee privacy notice / Sponsor duties notice (visa and sponsorship) / Other);
    - how people confirm: **Read and accept** (tick box) / **Read and sign** (type full name);
    - audience: Everyone / Departments / Locations / Named people / Employees with a visa on file;
    - accept within N days*;
    - send to new starters automatically.
  - **Detail page:** who has accepted, signed, is pending or is overdue; remind pending people; new version (re-request acceptance).
- **My Documents:** documents to read and accept/sign, with an embedded PDF viewer, "I have read and accept" or a typed-name signature, and a timestamped, IP-stamped receipt.

### 8.11 Recruitment
- **`/recruitment`:**
  - intro line explaining requisition → approval → posting → candidates → applications;
  - KPIs: Open requisitions, Live postings, Candidates, Applications in progress;
  - **Pipeline** bar with 8 clickable stages (Job Applied, Shortlisted, Interview, Offer Letter, Offer Accepted, Hired, Rejected, Withdrawn) that filter the Applications tab;
  - tabs: Requisitions / Postings / Candidates / Applications, with counts.
- **Requisitions:**
  - sheet: job title, department, headcount, grade, budget from/to + per (Year/Month/Hour), justification;
  - status select: Draft / Open (approve) / On hold / Filled / Cancelled. Only `recruitment.requisition.approve` can set Open, which stamps "Approved {date} by {name}";
  - Cancel asks for confirmation.
- **Postings:**
  - sheet: requisition* (Open only), title, visibility (Internal / External), location, job code, SOC code (with a "Find code" button that runs the SOC checker on the description), vacancies, posted date, closing date, contact email/phone, salary from/to + per, hours a week, job description (with a "Start from template" button and a "Writing it safely" expandable guide on inclusive, non-discriminatory wording), visa sponsorship (Not stated / Available / Considered for the right candidate / Not available);
  - table columns: posting, visibility, closes, vacancies, status (Draft / Open / Closed with confirmation), public link (External + Open only, with Copy), actions;
  - closing a posting stops applications and disables the public link immediately.
- **Public careers:** `/careers/{company-slug}` (list of External + Open postings) and `/careers/{company-slug}/{posting-slug}`:
  - posting detail (company logo, title, location, salary, hours, description, visa sponsorship statement, closing date);
  - **Apply** form: name, email, phone, CV (optional, scanned), "what you'd bring" text, privacy notice consent, Turnstile.
  - Creates the candidate and application with `applied_via=careers_page`; sends a confirmation email to the applicant and a notification to recruiters.
- **Candidates:**
  - add sheet: first, last, email, phone, source;
  - profile header: initials, name, RTW status, source, email; actions Apply to posting, Convert to employee;
  - tabs: Overview (RTW gate notice, details, documents, applications), Applications (+ "Apply to posting" select), Right to Work, Documents, **Sponsorship check** (new: runs the SOC checker with their CV, see 8.17).
- **Application detail `/recruitment/applications/{id}`:**
  - title "{Candidate} — {Posting}", stage chip, RTW status, "Waiting on…" hint, primary "Move to {next stage}";
  - Stepper of 6 forward stages with timestamped history;
  - "Move to stage" select. **Forward moves go one step at a time** (server-enforced, with error "The next step from X is Y"). Backward moves are allowed. Rejected/Withdrawn end the application;
  - **Interviews (new):** schedule (date/time, duration, in person/video/phone, location or link, interviewers), outcome, notes; an .ics invite is emailed to interviewers and the candidate;
  - **Offers:** create (role title, salary GBP + per, start date) → Sent → Accepted / Declined;
  - **Convert to employee:** requires **an Accepted offer AND a Verified RTW check** (enforced server-side). It creates the employee (prefilled), links documents and the RTW check, sets the hire date to the offer start date, and sets the application to Hired.

### 8.12 AI features (assistant, letters, reminders, SOC) — privacy by design
- **Provider:** Anthropic Claude via `api/app/integrations/anthropic.py`. Only the API calls it.
- **Assistant panel** (the floating button can be hidden per user; the name is configurable, default "Assistant"):
  - suggestion chips: "Give me a compliance summary", "How many people are in today?", "How much leave do I have left?", "Show me the details for…";
  - answers stream; each says "AI-generated from your company's records".
- **Architecture (tool use):**
  - The model never sees the database. It calls **read-only tools** that execute **as the current user, with their permissions and tenant**: `get_compliance_summary`, `get_attendance_today`, `get_leave_balance(employee_label?)`, `get_employee_facts(employee_label)`, `get_upcoming_expiries`, `get_open_approvals`, `count_employees(filters)`.
  - Tools return **aggregate figures or a short fact sheet**.
  - Employee names are replaced by labels (`Employee A`) before sending; the UI maps labels back to names after the response.
  - **Never sent:** NI numbers, bank details, passport or visa numbers, share codes, CoS numbers, health or sickness details, salary, home address, date of birth.
- **Guardrails:** a system prompt that refuses legal advice and non-HR questions, cites figures only from tool results, and says "I can't see that" when permission is missing. Rate limit 30 per hour per user. Usage is logged as metadata only.
- **Letter drafting and reminder wording:** generic placeholders only; no identifiers.
- **SOC matching and resume match:** see 8.17. Job descriptions and CVs are sent to AI **only after an explicit user action**. CVs have contact details (email, phone, address) stripped first.
- **Settings:** a Company Admin can turn AI features off for the company (Company → Details → "AI features").

### 8.13 Org chart (`/organogram`)
- **Canvas:**
  - tree built from the Reporting Authority on current assignments;
  - pan by drag, zoom with buttons and pinch, search to jump to a name;
  - a click opens the inspector with a person summary;
  - "Show visa status" toggle (adds RTW/visa chips);
  - "Download PDF" (multi-page for large teams);
  - **List view** toggle;
  - "Unassigned" section for people without a manager.
- **Hierarchy levels:** an editable ordered list (default "Director"; "Add level"). Used as labels only.

### 8.14 Learning
- **Courses are original content written by us** from official sources (GOV.UK, ACAS, EHRC), stored in `courses` with source title, publisher, URL, source last-updated date, content-reviewed date and an OGL attribution where needed. They are edited only in super-admin.
- **Launch with 8 courses** (write them fresh in Phase 13; 15–25 min, 5–6 sections each, 5-question check):
  1. Employment rights essentials
  2. Employment status: employee, worker or self-employed
  3. Equality and discrimination at work
  4. Preventing sexual harassment: the employer duty
  5. Bullying and harassment at work
  6. Agency workers' rights
  7. Inclusive recruitment: writing the role
  8. Inclusive recruitment: attracting candidates
- **`/learning`:**
  - KPIs: Assignments, Not started, In progress, Completed, Overdue;
  - views: Report (table with search, course, status and department filters, export xlsx) / Courses (cards with duration, sections, audience, assigned/completed/overdue counts, sources & review box, "Assign this course");
  - **Assign wizard:** 1 Courses → 2 People (everyone / departments / named) → 3 Review (one due date).
- **My Learning:** Assigned to me / All courses; course player (section by section, progress saved, keyboard friendly), check questions, pass mark, then a **certificate PDF** with a public reference.
- **Public `/verify`:** enter a certificate reference to see holder name, course title, completion date and status. It never shows other personal data. Rate-limited.

### 8.15 Company settings and user access (`/company/*`, inset grouped list style)
- **Overview:** company card (logo, name, status, default address) and grouped rows with counts:
  - **Company:** Details, Locations, Departments, Designations, Key personnel (x of 4), Compliance documents (x of 18);
  - **Time:** Working pattern & holidays, Leave settings, Trading hours;
  - **Pay:** Bank accounts, Tax codes, Payment types, Pay bands, Pay schedules;
  - **Access & billing:** User Access, Billing, Data export, Delete account.
- **Details** (edit sheet):
  - logo, company name*, trading name, Companies House number (with an optional lookup that auto-fills name and address via the Companies House API);
  - legal structure: Private company limited by shares / Charitable incorporated organisation / Industrial and provident society / General partnership / Limited liability partnership / Scottish limited partnership / Limited partnership / Community interest company / Private company limited by guarantee / Public limited company / Sole proprietorship / Other;
  - trading period: 0–6 months / over 6–12 / over 12–18 / over 18–36 / over 36 months;
  - sector: the 21 UK SIC 2007 sections;
  - changed name in the last 5 years? (Y/N + previous name); illegal-working penalty in the last 3 years? (Y/N + status);
  - contact email, phone, website, timezone*, bank holiday region, AI features on/off.
- **Locations:** name, postcode lookup, address lines 1–3, city, county, country, default.
- **Departments:** name.
- **Designations:** title, department (required), optional SOC code.
- **Key personnel:** Authorising Officer, Key Contact, Level 1 User, Level 2 Users (many). Fields: first, last, designation, phone, email, proof of ID file, "same as Authorising Officer". Each card explains the role in one line.
- **Compliance documents (18 types):**
  1. PAYE and Accounts Office reference letter from HMRC
  2. Latest RTI from accountant
  3. Employer's liability insurance certificate
  4. Proof of business premises (tenancy agreement)
  5. Copy of lease or freehold
  6. Business bank statement month 1
  7. Business bank statement month 2
  8. Business bank statement month 3
  9. Signed annual accounts (if over 18 months old)
  10. VAT certificate (if registered)
  11. Food hygiene rating (food businesses)
  12. Registered business licence/certificate
  13. Franchise agreement
  14. Governing body registration
  15. Health & safety rating copy
  16. Audited annual accounts
  17. Regulatory body certificate (e.g. ACCA, FCA, Ofcom, IATA, ARLA)
  18. Other
  - Each record has an optional expiry date and feeds reminders.
- **Working pattern & holidays**, **Leave settings** (8.6), **Trading hours** (per day open/opens/closes, autosave per row with a "Saved" tick).
- **Bank accounts** (masked, encrypted), **Tax codes** (code, reference, deduction %), **Payment types** (name, minimum hourly rate), **Pay bands** (name, min/max annual, currency), **Pay schedules**.
- **User Access:**
  - users table (User, Roles, Status, Two-step, Linked employee, Actions); filters for role and status; banner "N unlinked users";
  - **Invite user** sheet: first, last, email, role radio cards with a one-line description each, then a single-use invite link by email;
  - row actions: change role, link/unlink employee, suspend/reactivate, reset two-step (step-up), resend invite;
  - **Two-step verification policy** radio cards: Optional for everyone / Required for Company Admins / Required for all users;
  - **"What can each role do?"** viewer: pick a role to see a grouped list of every screen and action.

### 8.16 Billing and account lifecycle
- **Plans:** Free / Annual (£50 per year, Stripe subscription) / 10-year (£240 one-off Stripe Checkout payment; stores `subscription_ends_at = +10 years`). Prices are configured by Stripe price id (`STRIPE_PRICE_ANNUAL`, `STRIPE_PRICE_TEN_YEAR`); never hard-code amounts in logic.
- **Entitlements:**
  - `is_entitled` = an active paid plan.
  - Free or lapsed = **read-only**: every write endpoint returns `402 PLAN_REQUIRED` except auth, profile, billing, export and deletion. Adding employees requires paid.
  - The UI shows an upgrade sheet.
- **`/company/billing`:**
  - plan card (plan, price, cycle, renews, status, customer since);
  - 14-day money-back banner with its end date;
  - **Cancel subscription:** within 14 days, an automatic full refund through the Stripe Refunds API; after 14 days, cancel at period end;
  - "Payment details & invoices" opens the Stripe Billing Portal session;
  - plan change annual ↔ 10-year: handled by support in v1 (button "Contact support"), automated later.
- **Webhooks** (`/webhooks/stripe`): checkout.session.completed, invoice.paid, invoice.payment_failed (grace 7 days + emails), customer.subscription.updated/deleted, charge.refunded. Idempotent.
- **Data export:** a full zip (CSV per table + documents) is generated by a worker, emailed as a link valid for 7 days, and requires step-up.
- **Delete account:**
  - explanation of what is deleted; offer an export first;
  - a 6-digit code is emailed; entering it confirms;
  - the deletion is scheduled for +7 days, other Company Admins and support are notified, and it can be withdrawn until then;
  - the worker purges all tenant rows and R2 objects and keeps only a minimal audit stub (company id, deletion date) and Stripe/accounting records required by law;
  - a confirmation email is sent.

### 8.17 Sponsorship Job Checker (SOC finder) — new flagship feature
**Goal:** a client types a rough job title and description (and optionally uploads the candidate's CV). The app shows:
- the correct **SOC 2020 code**;
- the **official description**;
- **eligibility** (which table, TSL/ISL status with end dates, or ineligible);
- the **going rate** and **general threshold** for their hours;
- the reduced rates the candidate actually qualifies for (new entrant, PhD, STEM PhD, ISL, health/education);
- **pass/fail against the offered salary**;
- **dependants** and English level notes;
- a **CV match** with evidence, gaps and suggestions;
- a saved, dated PDF report.

**Rules knowledge, verified 1 Nov 2026 (seed `rules_versions` v1 from the official pages, never from memory):**
- **Appendix Skilled Occupations** (GOV.UK, updated 29 Oct 2026):
  - Table 1: about 91 RQF 6+ codes, median ASHE going rates, options A–E;
  - Table 1a: about 170 RQF 3–5 codes, transitional for those with permission before 22 Jul 2025, unless on the TSL;
  - Tables 2 / 2a / 2aa / 2b: 25th-percentile rates for options F–J and older transitional cases;
  - Tables 3 / 3a: health and education national pay scale codes (option K);
  - Tables 4 / 5: pay-band rates;
  - Table 6: ineligible codes.
  - Going rates assume 37.5 h/week (doctors 40). Pro-rate as annual ÷ 37.5 × weekly hours. Only the first 48 h count.
- **General thresholds:** £41,700 standard (option A); £37,500 (PhD, 90% of going rate); £33,400 (STEM PhD 80% / ISL 80% / new entrant 70%); £25,000 floor for option K (health/education on national pay scales) and the F–J options for eligible transitional/health applicants. **Not pro-rated for part-time.**
- **New entrant:** under 26 on application, or a recent UK student/graduate (qualifying course), or working towards a UK-regulated professional qualification, registration or chartered status, or in a listed postdoctoral role. 70% of the going rate, minimum £33,400. Maximum 4 years in total.
- **ISL (Appendix Immigration Salary List, updated 29 Oct 2026):** 25 entries, some with conditions or Scotland only. Removal date **31 Dec 2026**, except 6135/6136 care workers, **22 Jul 2028**. The **CoS assignment date** decides.
- **TSL:** the interim list (about 52 RQF 3–5 codes, Appendix Skilled Worker SW 6.1A) expires **31 Dec 2026**. No salary discount; no dependants for new RQF 3–5 TSL workers.
  - The MAC Stage 2 report (23 Jul 2026) recommended **28 occupations** for 1 Jan 2027 – 30 Jun 2028.
  - **The Home Office decision was not yet published at plan time: load the list only when the Immigration Rules are updated, and show "pending government decision" until then.**
- **English:** B2 for new applicants (verify the current rule and date on GOV.UK).
- **Flow screen** (`/sponsorship-checker`, also embedded as "Find code" in postings, candidate tab and visa form):
  1. **Inputs:** job title (type-ahead over the ONS index); job description (paste, or pulled from the posting); weekly hours; offered salary + per; work location nation; CoS assignment date (default today); applicant situation (outside UK / switching from Graduate / Student / other / extending / changing employer; already in Skilled Worker before 22 Jul 2025 or before 4 Apr 2024); qualifiers (under 26; UK student/graduate in last 2 years; professional training; PhD relevant; STEM PhD; postdoctoral; health or social care employer); optional CV upload.
  2. **Matching pipeline (API):**
     - a. normalise the title;
     - b. candidate retrieval: trigram + full-text over `soc_index_entries` and vector search (`fastembed` locally) over index titles and unit-group descriptions, giving the top 10 codes;
     - c. re-rank with Claude (`ANTHROPIC_MODEL_MAIN`). Send the job title and description and the 10 candidates' official descriptions and tasks; get back a JSON ranking with a confidence of 0–100, the duties that matched, and why the runner-ups lost;
     - d. the rules engine evaluates the top 3 codes deterministically (no AI) for the date given.
  3. **Results page:**
     - **best match card** (code, title, confidence, "why", official description and tasks, typical titles, "Check on CASCOT" link);
     - 2 alternatives;
     - **Eligibility** chip (Eligible / Eligible — transitional only / On TSL until… / On ISL until… / Not eligible (Table 6));
     - **Salary table** for the given hours: general threshold, going rate (pro-rated), and each option the applicant qualifies for, with **minimum required = max(threshold, % of going rate)**, highlighting the applicable lowest option;
     - **verdict** against the offered salary: ✓ meets / ✗ short by £X / needs Y more hours;
     - dependants allowed?; notes (ISL condition text, nation limits, 48 h cap).
  4. **CV match** (optional):
     - parse PDF/DOCX text (strip contact details);
     - Claude compares it with the chosen code's tasks and the job description and returns a match score of 0–100, evidence bullets quoting the CV, gaps (missing qualification or experience), and **suggestions** (e.g. "Code 3544 Data analysts fits the duties better", "Ask for evidence of X").
  5. **Confirm and save:** a human must click "Confirm this code". This saves to `soc_checks` and generates a PDF report (inputs, chosen code, rules version, rates, verdict, CV match, disclaimer, date). It fills `postings.soc_code` / `sponsor_documents.soc_code` / `designations.soc_code`.
- **Guardrails (must be in the prompt and the UI):**
  - Suggestions must describe the **genuine** job. The tool never proposes rewording duties to reach a higher-paid or eligible code; if asked, it explains that misdescribing a role risks licence revocation.
  - Always show "General guidance, not legal or immigration advice" and the rules version + date.
  - If the confidence is below 60, show "Low confidence — check with an adviser or CASCOT".
- **Rules data maintenance (super-admin):**
  - a daily job watches the GOV.UK Immigration Rules "updates" page and the three appendix pages (ETag/hash);
  - on a change it imports into a **draft** `rules_version` (HTML table parser with unit tests on saved fixtures), shows a **diff** (codes added/removed, rate changes) and requires a Platform Admin to **Publish**;
  - every saved check keeps its rules version.
- **ONS data:** import the SOC 2020 coding index (xlsx/CSV, about 30,110 entries, OGL v3.0) and the SOC 2020 structure/descriptions (unit groups, tasks, entry routes) from ONS in `data/import_soc.py`, then compute embeddings at import.
- **Public free tool:** `/resources/tools/sponsorship-job-checker` (title search + salary table, no CV, no AI rerank unless Turnstile passes, rate-limited).

### 8.18 Super-admin back office (`admin.DOMAIN`)
- **Access:**
  - Platform Admin only, with MFA; optional IP allowlist; separate session cookie name;
  - every page view and action is audited;
  - big red header bar "Platform admin" so it's never confused with a tenant.
- **Pages:**
  - **Overview:** signups (day/week), active companies, paid vs free, MRR/ARR estimate, churn, refunds, error rate, job queue health, register freshness.
  - **Companies:**
    - search/filter (plan, status, created, last active);
    - detail page: profile, plan & Stripe links, users (reset MFA, resend verification), counts, storage used, audit trail, notes;
    - actions: suspend/reactivate (with reason), extend plan (comp), mark for deletion.
  - **Support mode (impersonation):** requires a reason and a ticket ref. Read-only by default; a write-enable toggle needs owner level and a second confirmation. A banner appears in the tenant UI. It auto-expires after 30 min. A **company-visible audit entry** is recorded.
  - **Subscriptions & refunds:** list from the DB + Stripe; issue refunds (owner level).
  - **Deletion & export requests** queue with status.
  - **Users:** global search by email, lock/unlock.
  - **Rules data (SOC):** versions, diff, publish, rollback.
  - **Content:** courses editor (sections, quiz, sources, review date, publish), templates, guides (MDX upload with preview), sponsor dossier links, announcement banner (scheduled, per region).
  - **Sponsor register:** last import, row counts, errors, rerun import.
  - **Jobs:** queue, failures, retry.
  - **Contact messages** inbox (mark handled).
  - **Platform audit log** (filter, export).
  - **Settings:** terms version publish (forces re-acceptance), feature flags.

### 8.19 Global UX: search, notifications, shortcuts
- **Command palette (⌘K / Ctrl K):** Recent pages (stored in localStorage `brand.recentPages`, max 8), Pages (all routes the user may access), People (live search: employees and candidates), Actions (Add employee, Request leave, Record attendance, Run sponsorship check…).
- **Keyboard shortcuts (`?` sheet):**

| Keys | Action |
|---|---|
| ⌘K | Search |
| G then D / E / R / C / L / A / T | Dashboard, Employees, Recruitment, Compliance, Leave, Attendance, Rota |
| N | New (contextual) |
| / | Focus list search |
| [ | Collapse sidebar |
| Esc | Close the top layer |
| J / K | Move row |
| Enter | Open row |
| . | Row menu |

- **Notifications bell:**
  - "Needs attention" (compliance) plus personal notifications (approvals, policy to sign, shift published, course assigned, reminder received);
  - mark all read; link to the item;
  - email digests are configurable per user (immediate / daily / off).
- **Toasts:** with undo for reversible actions.

### 8.20 Public website (original copy; brand from config)
- **Pages:**
  - Home;
  - Sponsor compliance (+ "Reporting duties" deep page);
  - Features (one section per module, with real screenshots from seeded demo data);
  - Pricing (two plan cards, headcount slider, "why so cheap", what's included, FAQ, refund terms summary);
  - Security;
  - About;
  - Careers (powered by our own careers module for our company);
  - Contact (name, company, email, topic: Sponsor licence compliance / Simple HR for my business / Pricing or billing / Help setting up / Partnership or reseller / Something else / Data protection complaint; message; Turnstile; a 1-working-day reply promise in copy);
  - Accessibility statement;
  - Verify certificate;
  - Login; Setup.
- **Resources hub:** Guides, Tools, Templates.
  - **Guides** (MDX, original, each with "Sources" list, last-reviewed date and disclaimer): Right to Work checks; Follow-up Right to Work checks; Right to Work changes from 1 October 2026 (verify); Sponsor licence audit preparation (with an interactive 26-question self-test and score); Statutory holiday entitlement; Sponsor reporting duties.
  - **Templates** (original, downloadable DOCX/PDF): Job description (+ worked example), Offer letter (standard / sponsored worker / hourly or casual), Right to Work check checklist, New starter checklist.
  - **Tools** (Section 10): 14 calculators + the Sponsorship Job Checker.
- **Comparison pages:** `/compare/hr-software-uk`, `/compare/sponsor-compliance-software-uk`, and `/vs/{competitor}` templates. **Only publish with prices verified from each competitor's public pricing page, showing the date checked and a source link** (the owner must approve each before publishing; leave them unpublished by default).
- **Legal:** Terms, Privacy, Cookies (+ preferences), DPA, Subprocessors, AI policy, Complaints (with form), Refunds & cancellation, Resources disclaimer, Register terms, Accessibility. Draft them from our real architecture, marked **"DRAFT — requires solicitor review"**, and list them in `PROGRESS.md` as an owner action.
- **Cookie consent:**
  - only necessary cookies by default;
  - optional marketing pixels (Meta, Reddit, Google Ads) load **only after consent and only on marketing routes**, never in the app;
  - consent is stored in localStorage `brand.cookieConsent` `{version, marketing, decidedAt}`;
  - a "Cookie settings" link appears in the footer.
- **SEO:**
  - per-page metadata and canonical URLs;
  - generated OG images (`opengraph-image.tsx`);
  - JSON-LD (Organization, WebSite, BreadcrumbList, FAQPage where relevant, SoftwareApplication);
  - `sitemap.xml` (+ sponsor sitemaps); `robots.txt`;
  - Lighthouse ≥ 95 on all four categories for marketing pages.
- **Demo video section:** a placeholder component that accepts an MP4 path with chapters. The owner records a real walkthrough later.

### 8.21 Public UK sponsor licence register (`/sponsors`)
- **Ingest job:**
  - runs each working day at 10:00 and 16:00 UK time;
  - finds the latest "Register of licensed sponsors: workers" CSV on its GOV.UK publication page (parse the page; never hard-code the file URL);
  - downloads it and stores a hash; if unchanged, skips;
  - parses it, normalises names, upserts `register_sponsors`, writes `register_entries` for this publication, computes `register_changes` versus the previous publication, and fuzzy-matches added versus removed (possible renames);
  - geocodes the town via the ONS Index of Place Names (bulk file) to an ITL1 region with a precision flag;
  - optionally matches Companies House numbers via the Free Company Data Product (monthly bulk file) to get the SIC section.
- **Pages:**
  - **Explore:** search (sponsor/town/route); filters for region, route, rating and industry; a publication timeline slider with a compare window (7 d / 30 d / 90 d / 180 d / 1 yr / start); a "register pulse" bar chart (added above / removed below); views Map / Trend / Table / List;
  - an **original SVG map** of the 12 UK ITL1 regions (from ONS boundary data, simplified) with counts and daily deltas;
  - sections: sponsors by town, then and now, regions at a glance, routes, ratings, types, placement precision, industries, newest on the register.
  - `/sponsors/regions/{region}` (12 pages).
  - `/sponsors/changes` (bulletin list) and `/sponsors/changes/{date}` (added / no longer listed / net / returned, median of the last 28, where the changes were, possibly the same sponsor, the list).
  - `/sponsors/profile/{id}/{slug}`: current entry (routes, licence type, rating), licence lifeline (first seen, changes), recorded changes, region breadcrumb. Rendered on demand with ISR caching (revalidate 6 h). About 128k pages.
  - `/sponsors/methodology` and register terms; "Report a problem with an entry" form.
- **Attribution:** "Contains public sector information licensed under the Open Government Licence v3.0", plus a statement that we are independent of the Home Office and that a licence doesn't mean the employer is hiring.
- **Sitemaps:** split, at most 45k URLs each, under `/sponsors/sitemap.xml`.

---

## 9. Build phases and tasks (do them in this exact order)

Each task has **Do** and **Done when**. Every task also inherits the Definition of Done (0.2).

### Phase 0 — Foundations and guard-rails
**T0.1 Repo initialisation**
- **Do:**
  - `git init`;
  - create the layout from Section 3, `README.md`, `PROGRESS.md` (copy every task id from Section 9 as an unchecked list plus an "Owner actions needed" section), `SECURITY.md`, `.gitignore`, `.editorconfig`, `brand.config.ts` (name "Brand", tagline placeholder, accent `#0071E3`).
- **Done when:** the tree matches Section 3 and `git status` is clean after the first commit.

**T0.2 Secret guard-rails before any code**
- **Do:**
  - add `.gitleaks.toml`; `.pre-commit-config.yaml` (gitleaks, ruff, ruff-format, prettier, eslint);
  - `.env.example` with **names only** (copy the variable list from `deployment-requirements.txt`);
  - `scripts/check-public-env.mjs`, which fails if any `NEXT_PUBLIC_*` outside the allowlist exists;
  - `scripts/scan-bundle.mjs`, which fails if the built bundle contains secret prefixes.
- **Done when:**
  - committing a fake `sk_live_...` string is blocked locally;
  - `.env` is ignored (checked with `git check-ignore .env`).

**T0.3 Local stack (Docker Compose)**
- **Do:** Compose services postgres:16 (with pgvector), redis:7, minio (bucket `files-dev`), mailpit, clamav (clamd), stripe-cli (profile `stripe`), with healthchecks and named volumes.
- **Done when:** `docker compose up -d` gets all services healthy, and `README.md` documents it.

**T0.4 API skeleton**
- **Do:**
  - FastAPI app factory, `core/config.py` (pydantic-settings, all secrets as `SecretStr`, an environment enum), structlog JSON logging with the redaction processor, request-id middleware, an error handler (envelope `{"error":{"code","message","field?","request_id"}}`), and `/health` + `/ready` (DB and Redis checks);
  - gunicorn config; Dockerfile (multi-stage, non-root user, slim, pinned digests); `uv` lockfile.
- **Done when:**
  - `pytest` passes;
  - `ruff` and `mypy --strict` are clean;
  - the container runs as non-root;
  - the logs never print settings values (a test asserts `repr(settings)` has no secret values).

**T0.5 Database layer**
- **Do:**
  - async SQLAlchemy engine; Alembic;
  - roles `app_owner` (migrations) and `app_user` (runtime, no BYPASSRLS);
  - the `TenantSession` dependency (`SET LOCAL app.company_id`); RLS helper for migrations; UUID v7 default; timestamps mixin;
  - extensions: pgcrypto, pg_trgm, unaccent, vector, citext.
- **Done when:** a sample tenant table with RLS passes an isolation test (company A cannot select company B rows even with raw SQL as `app_user`).

**T0.6 Web skeleton**
- **Do:**
  - Next.js 16 app with TypeScript strict, Tailwind v4, shadcn/ui init, ESLint and Prettier;
  - route groups `(marketing) (auth) (app) (admin)`;
  - `middleware.ts` with host routing (admin host only), nonce-based CSP and the security headers from 4.6;
  - Dockerfile (standalone output, non-root).
- **Done when:**
  - the dev server runs;
  - securityheaders-style checks pass in a Playwright test that reads the response headers;
  - the `(admin)` routes give a 404 on the main host.

**T0.7 Typed API client pipeline**
- **Do:** `pnpm gen:api` exports OpenAPI from FastAPI, then `openapi-typescript`, then `web/lib/api/schema.ts`, plus a `openapi-fetch` client with credentials and the CSRF header; CI checks that the generated file is up to date.
- **Done when:** a sample `/health` call is typed end to end.

**T0.8 CI pipelines**
- **Do:**
  - `.github/workflows/ci.yml`: lint, type-check and tests for api (Postgres/Redis services) and web, build, gitleaks, semgrep, pip-audit, pnpm audit, Trivy image scan, bundle secret scan, public-env check;
  - `security.yml` (weekly + manual): ZAP baseline against staging;
  - Dependabot config.
- **Done when:** CI is green on the main branch, and a PR containing a fake secret fails.

**Phase 0 gate:** write the summary in `PROGRESS.md`.

### Phase 1 — Design system and app shell
**T1.1 Tokens and theming:** CSS variables from 5.3 (light/dark); the typography scale (5.2); radius, elevation and spacing utilities; motion presets; the `data-theme` switch; `next/font` Inter var. Done when a `/design` page (dev-only) renders all tokens in both themes.

**T1.2 Primitive components:** build every component in 5.7 under `components/ui/`, with Storybook-style docs on the `/design` page (each in all states). Done when axe shows 0 serious issues on `/design`, and keyboard interaction works for Dialog, Sheet, Menu, Combobox, SegmentedControl, DatePicker and DataTable.

**T1.3 App shell:**
- translucent sidebar with groups (5.6), collapse animation, mobile tab bar + "More" sheet, toolbar (breadcrumbs, search field, help, bell, avatar menu);
- empty `(app)` pages for every route in the sidebar, using EmptyState;
- the "Loading your workspace…" splash.
- **Done when:** Design QA (5.12) passes for the shell at 4 widths × 2 themes.

**T1.4 Command palette and shortcuts:** CommandPalette (static pages for now), the keyboard shortcuts sheet, and the global shortcut handler from 8.19. Done when every shortcut works and is listed.

**T1.5 Marketing layout:** marketing header (translucent, mobile menu), footer (4 columns), the section components (hero, feature grid, alternating band, CTA band, FAQ accordion, pricing cards, slider), and the cookie consent banner + preferences dialog (8.20). Done when the Design QA passes and Lighthouse is ≥ 95 on a sample page.

### Phase 2 — Backend core (identity, tenancy, RBAC, audit, files, email)
**T2.1 Models:** companies, users, memberships, platform_admins, sessions, invitations, email_tokens, terms, audit_events (with an append-only trigger), files, notifications. Done when migrations apply and roll back cleanly.

**T2.2 Crypto:** `core/crypto.py` (AES-256-GCM with key ids, blind index HMAC, mask helpers); a SQLAlchemy `EncryptedString` type; a key rotation command `python -m app.cli rotate-keys`. Done when round-trip, tamper-detection and rotation tests pass.

**T2.3 Sessions and auth service:** argon2id hashing, breached-password check (HIBP range API with timeout and fallback), opaque session tokens (hashed) in Redis plus a DB record, idle/absolute expiry, rotation, CSRF double-submit, rate limits, lockout, login alerts. Done when the tests from 4.7 for auth pass.

**T2.4 Auth endpoints:** signup (company + admin, free plan, Turnstile), verify email, resend, login, logout, me, forgot/reset, change password, MFA setup/verify/challenge/disable + recovery codes, step-up, accept terms, accept invite. Done when all return the documented schemas and the enumeration-safe behaviour is tested.

**T2.5 RBAC:** `rbac_matrix.py` (Section 7), the `require(perm)` dependency with `_own`/`_reports` scope resolvers, and the reports-graph resolver (Reporting Authority and Leave Sanctioning chains, with a recursive CTE, cached per request). Done when the RBAC matrix test (all roles × all endpoints) is wired and running. It will grow with each module.

**T2.6 Audit service:** `audit.record(action, entity, before, after, reason)` within the same transaction; sensitive-field masking; `GET /audit-events` (+ CSV export). Done when the tests prove events are written atomically and cannot be updated or deleted.

**T2.7 Files:** R2/MinIO client (S3), the upload endpoint (stream → size, extension and magic-byte check → ClamAV → store → `files` row), presigned 60 s download, and orphan clean-up job. Done when the EICAR test is rejected, a wrong magic byte is rejected, and a clean PDF is accepted.

**T2.8 Email:** Resend client (Mailpit in dev); branded HTML + text templates (verification, reset, invite, login alert, notifications digest, reminder nudge, leave decision, policy request, deletion code); outbox table + ARQ job with retries; never include sensitive data in emails. Done when the Mailpit screenshots of each template are in `docs/screenshots/email/`.

**T2.9 Worker and scheduler:** ARQ worker service, cron registry (empty jobs registered: reminders_daily, rtw_status_daily, register_ingest, bank_holidays_weekly, rules_watch_daily, retention_purge_daily, backups_nightly, deletion_executor_hourly), and job audit logging. Done when the worker starts and runs a sample job in tests.

### Phase 3 — Auth UI and onboarding
**T3.1:** `/login`, `/login/mfa`, `/forgot-password`, `/reset-password`, `/verify-email`, `/accept-invite` built to 8.1 with the full Design QA.
**T3.2:** the `/setup` two-step wizard + "Check your inbox" screen + Turnstile.
**T3.3:** terms gate, MFA enrolment flow (QR, confirm, recovery codes), MFA policy enforcement on next request.
**T3.4:** the signed-in session bootstrap (`/auth/me` provider, permission-aware sidebar, free-plan banner, 402 handling with the upgrade sheet).
- **Done when (phase):** Playwright E2E covers signup → verify (Mailpit) → dashboard → logout → login with MFA → recovery code login → password reset.

### Phase 4 — Company settings
**T4.1:** Company overview + Details (incl. the Companies House lookup via the API key, behind a feature flag) + logo upload.
**T4.2:** Locations (postcodes.io lookup), Departments, Designations.
**T4.3:** Key personnel (4 roles, proof of ID upload).
**T4.4:** Compliance documents (18 types, expiry).
**T4.5:** Working pattern, bank-holiday import job (GOV.UK JSON) and holiday types + company holidays (`/holiday-management`).
**T4.6:** Trading hours (autosave per row).
**T4.7:** Bank accounts (encrypted), Tax codes, Payment types, Pay bands, Pay schedules.
- **Done when (phase):** every page is in inset-grouped style, the RBAC tests cover the settings permissions, and audit events exist for every change.

### Phase 5 — Users and access
**T5.1:** User Access list, filters and the "N unlinked users" banner.
**T5.2:** invite flow (single-use link), role change (last-admin protection, admin-only for the Company Admin role), suspend/reactivate, reset 2FA (step-up), link/unlink employee (after Phase 6 exists, add the link picker and re-test).
**T5.3:** the MFA policy setting and the "What can each role do?" viewer generated from `rbac_matrix.py`.

### Phase 6 — Employees
**T6.1:** employee model + migrations (6.3); list page with pills, filters, deep links, keyboard nav, summary line; archived list.
**T6.2:** create page (essentials) and the unique-number rule.
**T6.3:** profile header + Overview tab + lifecycle status with inline confirm + 48 h opt-out + "permanently delete record created by mistake" (guarded).
**T6.4:** Personal tab (details, address with lookup, emergency contacts, identity and bank with mask/reveal + step-up + audit).
**T6.5:** Employment tab (hire date change with reason, effective-dated assignments + history, responsibilities, previous employment, education, training, memberships).
**T6.6:** Salary (compensation history, NMW check, hidden until shown, permission-gated).
**T6.7:** Documents tab (categories, payslips sub-tab, scan status) + employee record PDF.
**T6.8:** Leave, Attendance, Learning and Activity tabs as shells wired to later modules (they show real data once those phases land).
- **Done when (phase):** **no inline form auto-saves on button focus or clicks outside its own Save**; RBAC + isolation tests pass for every endpoint.

### Phase 7 — Right to Work and sponsor compliance
**T7.1:** RTW checks model, the 4 check-type forms (conditional fields), evidence picker + upload, history, correction flow, derived statuses view, evidence sheet PDF.
**T7.2:** Sponsor documents (6 types, versions, withdraw with reason, plan renewal), visa route enum, sponsored employees page.
**T7.3:** working-day calculator (bank holidays by region) with unit tests from GOV.UK examples; change of circumstances (form, deadline, mark as reported), org changes (20 days), company-wide CoC page.
**T7.4:** reminders engine (thresholds 90/60/30, due/scheduled/sent/snoozed), daily job, reminder register page, review drawer with an AI-drafted message (wired in Phase 14; until then use a template), send (in-app + email nudge) recording **who and when**.
**T7.5:** compliance hub: Needs attention queue, coverage, inspection readiness (5 checks), expiring 90-day buckets, activity feed + CSV, tools cards, dossier page (editable links seeded from GOV.UK).
**T7.6:** employee Sponsor Compliance tab + sponsor record PDF; the notifications bell "Needs attention" feed.
- **Done when (phase):** scenario tests pass, for example "RTW follow-up due in 21 days ⇒ Expiring + reminder due at the 30-day threshold"; "CoC logged on Friday before a bank holiday Monday ⇒ correct 10-working-day deadline".

### Phase 8 — Leave and holidays
**T8.1:** leave types (seed the 12; verify and store sources), leave settings (year start, negative balances).
**T8.2:** ledger + balance computation (pro-rata starters/leavers, part-time by personal pattern, bank holidays) with a strong unit-test suite.
**T8.3:** requests (own, on behalf), working-days counter, conflicts, approvals (LSA/approve permissions, no self-approval), notifications, attendance sync on approval.
**T8.4:** `/leave` Calendar / Requests / Balances; My Leave; My Approvals; employee profile Leave tab with Grant / Deduct / Set.
**T8.5:** year-end carry-over preview / overrides / commit.

### Phase 9 — Attendance, Rota, Work Log
**T9.1:** attendance records model, record sheet (upsert), workspace KPIs and range views, filters.
**T9.2:** import (template xlsx with a dropdown + CSV, preview with row errors, commit), bulk entry grid, exports (xlsx, PDF), absences this month.
**T9.3:** clock in/out (PWA install prompt, optional consented geolocation), timesheet approval for reports.
**T9.4:** shift types, late policies, day-off patterns (`/rota/settings`).
**T9.5:** rota week grid (quick add, cell sheet, row/day/week menus, copy/clear, warnings for leave/holiday/48 h/11 h rest, footer totals, not-scheduled list), publish + notifications, print PDF, My Shifts.
**T9.6:** Work Log (My Work Log + admin view with correct/remove audited).

### Phase 10 — Documents, policies and reports
**T10.1:** company documents (categories, review dates).
**T10.2:** reports (xlsx via worker; the 4 reference reports + 3 new).
**T10.3:** policies & sign-offs (3-step wizard, audiences, accept/sign, deadlines, reminders, versions, My Documents viewer and receipts).
**T10.4:** "Draft with AI" (wired to Claude in Phase 14; build the UI and API contract now with a feature flag).

### Phase 11 — Recruitment and public careers
**T11.1:** requisitions (sheet, statuses, approval permission + stamp, cancel confirmation).
**T11.2:** postings (full sheet, SOC field placeholder, JD template + "writing it safely" guide, statuses with confirmation, public link copy).
**T11.3:** candidates (add, profile tabs, documents, RTW tab reusing T7.1).
**T11.4:** applications (pipeline bar with counts, stepper, forward-one-step rule, history), interviews (schedule, .ics email), offers.
**T11.5:** convert to employee (both gates enforced server-side, prefilled employee, links RTW and documents).
**T11.6:** public careers pages + apply form (Turnstile, CV scan, confirmation email, recruiter notification).

### Phase 12 — Org chart
**T12.1:** tree API (from current assignments), hierarchy levels CRUD.
**T12.2:** canvas (pan/zoom/search/inspector/visa toggle), list view, unassigned section, PDF export.

### Phase 13 — Learning
**T13.1:** course model + super-admin course editor (minimal for now) + the course player.
**T13.2:** **write the 8 original courses** (Section 8.14). Each must have: sources with URLs, the source updated date, a content-reviewed date (today), OGL attribution if adapted, 5–6 sections, and a 5-question check with explanations. Have the owner review them (`PROGRESS.md` action).
**T13.3:** the assign wizard, report view + export, overdue job, My Learning.
**T13.4:** certificates (PDF, random reference) + public `/verify`.

### Phase 14 — Dashboard, notifications, search, and the AI assistant
**T14.1:** dashboard API (one aggregated endpoint, permission-aware) + all cards in 8.2 + the setup checklist.
**T14.2:** notifications (in-app list, bell badge, email digests and preferences).
**T14.3:** command palette live search (people, candidates, pages, actions).
**T14.4:** Anthropic integration (server-only), the redaction/pseudonymisation layer, read-only tools, streaming endpoint, assistant panel UI, rate limit, AI on/off per company, `ai_interactions` metadata logging.
**T14.5:** wire the AI in letter drafting (T10.4) and reminder wording (T7.4).
- **Done when (phase):** a test proves that no restricted field ever appears in the outgoing AI request payload. Fuzz the tool outputs and assert with a regex for NI, sort code, account number, passport, share code and salary patterns.

### Phase 15 — Sponsorship Job Checker (SOC)
**T15.1:** `data/import_soc.py`: download the ONS SOC 2020 coding index and structure/descriptions (store the downloaded file in `data/raw/` with its checksum and source URL), load `soc_index_entries` and `soc_unit_groups`, compute local embeddings (fastembed) into pgvector.
**T15.2:** rules-data importer: parse the GOV.UK Appendix Skilled Occupations (all tables), Appendix Immigration Salary List and the current TSL into a **draft** `rules_version` (with saved HTML fixtures for tests), plus `salary_rules` for options A–K from the caseworker guidance.
- Write the importer so that an owner can review the diff.
- **Never hand-type rates.**
- Publish v1 after the owner approves it (an action in `PROGRESS.md`).
**T15.3:** the rules engine (pure Python, no AI): eligibility, list status by CoS date and nation, pro-rated going rate, every option's minimum, verdict, dependants, notes. Add **golden tests** for at least 20 scenarios (e.g. 2134 at 37.5 h = £54,700; a new entrant with 2134 = max(£33,400, 70% = £38,300); an ISL bricklayer before and after 31 Dec 2026; a Table 6 code; a part-time 30 h worker; a TSL code with a dependants note).
**T15.4:** search and match API (trigram + vector retrieval, Claude re-rank with JSON schema output, confidence, explanations).
**T15.5:** CV match (PDF/DOCX text extraction, contact-detail stripping, Claude comparison, score, evidence, gaps, suggestions with the honesty guardrail).
**T15.6:** UI: `/sponsorship-checker` page + embedded "Find code" in posting, candidate tab, visa form and designation; results page; "Confirm this code"; PDF report; history list.
**T15.7:** daily rules watcher + super-admin diff/publish/rollback screen.
**T15.8:** public free version on `/resources/tools/sponsorship-job-checker`.

### Phase 16 — Billing, plans and account lifecycle
**T16.1:** the Stripe integration (server-only, restricted key): customers, Checkout for annual (subscription) and 10-year (one-off payment), Billing Portal session, webhook endpoint with signature + idempotency.
**T16.2:** entitlements (`402 PLAN_REQUIRED` for writes on free or lapsed plans; read-only UX; upgrade sheet), payment-failed grace and emails.
**T16.3:** the billing page, cancel with automatic refund within 14 days, end-of-period cancel after that.
**T16.4:** data export (worker zip, email link, step-up).
**T16.5:** delete account (6-digit code, +7 days schedule, withdraw, notifications, purge executor, final email).
- **Done when (phase):** Stripe test-mode E2E passes for both plans, refund, cancel, failed payment and webhook replay.

### Phase 17 — Super-admin back office
**T17.1:** platform admin auth (separate cookie, mandatory MFA, optional IP allowlist), admin host routing, red header bar.
**T17.2:** overview metrics, companies list/detail/actions, users search.
**T17.3:** support mode (impersonation) with reason, read-only default, expiry, tenant banner and audit.
**T17.4:** subscriptions and refunds, deletion and export queue, contact inbox.
**T17.5:** content tools (courses editor full, templates, guides, dossier links, announcement banner, terms version publish), feature flags.
**T17.6:** jobs dashboard (queue, failures, retry), register import status, rules data screens (from T15.7), platform audit log.

### Phase 18 — Public marketing site
**T18.1:** Home (original copy), Features (one section per module with **real screenshots** generated by a Playwright script from seeded demo data in both themes), Pricing (cards, slider, FAQ), Security, About, Contact (+ API + Turnstile), Accessibility, Careers (our own company's careers via the module), Sponsor compliance + Reporting duties.
**T18.2:** legal pages drafted as "DRAFT — requires solicitor review", cookie policy matching the real cookies, subprocessors matching the real vendors (Railway, Cloudflare, Resend, Anthropic, Stripe as independent controller, Sentry).
**T18.3:** SEO (metadata, OG images, JSON-LD, sitemaps, robots), Lighthouse ≥ 95, analytics only with consent.
**T18.4:** comparison page templates (unpublished by default; owner approval required).

### Phase 19 — Free tools, guides and templates
**T19.1:** the rates data files (`web/rates/*.json`) per Section 10, each value with `source_url`, `checked_on` and `valid_from`/`valid_to`. Verify every value from GOV.UK and HMRC **at build time** and record the result in `PROGRESS.md`.
**T19.2–T19.15:** build each calculator from Section 10 (one task each, in the order listed). Each is a pure TypeScript module with unit tests that use GOV.UK worked examples, plus a page with the shared calculator template: breadcrumb, "free tool" badge, quick answer, preset scenario chips, numbered step form, live result, "how it works", sources table, FAQ, disclaimer, CTA and more tools. Nothing entered is sent to the server.
**T19.16:** guides (MDX, original, sources, reviewed dates), including the interactive 26-question audit self-test.
**T19.17:** templates (original DOCX/PDF generated from MDX sources).
**T19.18:** the resources hub pages (`/resources`, `/resources/guides`, `/resources/tools`, `/resources/templates`).

### Phase 20 — Public sponsor register
**T20.1:** ingest pipeline (publication discovery, download, hash, parse, normalise, diff, possible matches), with fixtures and tests.
**T20.2:** geocoding (ONS Index of Place Names bulk load), ITL1 regions, the original simplified SVG map; Companies House bulk match (optional flag).
**T20.3:** Explore page (search, filters, timeline, pulse chart, map/trend/table/list, sections).
**T20.4:** region pages, change bulletins, profile pages (ISR), methodology, register terms, report form, sitemaps.

### Phase 21 — Security hardening pass
**T21.1:** run the whole 4.7 suite. Add missing tests until the RBAC matrix covers **every** endpoint.
**T21.2:** threat model doc (`docs/security.md`: assets, trust boundaries, STRIDE per component, mitigations).
**T21.3:** dependency, container and secret scans clean; CSP report-only check on staging, then enforce.
**T21.4:** pen-test style checks: IDOR on every `{id}` route, mass assignment (Pydantic `extra="forbid"`), SSRF (no user-supplied URLs fetched server-side except allowlisted GOV.UK/ONS/postcodes.io/Companies House), file path traversal, open redirects (allowlist `next=` paths), rate limits and lockout, session fixation, clickjacking, XSS (Markdown/MDX rendering sanitised), SQL injection (only parameterised queries).
**T21.5:** privacy review: data map, retention jobs active, export and deletion verified, AI payload test, logs and Sentry scrubbing verified.

### Phase 22 — Quality, performance, accessibility
**T22.1:** full E2E suite for the top 25 user journeys (signup→subscribe→add employee→RTW→reminder; leave request→approval; rota publish→My Shifts; requisition→posting→careers apply→interview→offer→convert; policy send→sign; course assign→complete→verify; SOC check→confirm→PDF; deletion with withdraw, …).
**T22.2:** performance budgets: API p95 < 300 ms on the main lists with 1,000 employees of seeded data; web LCP < 2.0 s, CLS < 0.05; add indexes as needed (EXPLAIN in tests for the main queries).
**T22.3:** accessibility audit on every page (axe 0 serious), screen-reader smoke test of the main flows, reduced-motion check.
**T22.4:** Design QA sweep with screenshots of every screen, light/dark × mobile/desktop, saved to `docs/screenshots/final/`.

### Phase 23 — Deployment (Railway + Cloudflare)
Needs the owner's accounts and keys from `deployment-requirements.txt`. **The owner sets secret values directly in Railway and Cloudflare dashboards. You never see or print them.** You may use `RAILWAY_TOKEN` from the environment for CLI deploys.

**T23.1:**
- **Railway services:** create the project `brand` with environments `staging` and `production`, and these services per environment:
  - `web` (Dockerfile `web/`);
  - `api` (Dockerfile `api/`, start: gunicorn);
  - `worker` (same image as api, start: `arq app.jobs.worker.WorkerSettings`);
  - `clamav`;
  - Postgres (with pgvector);
  - Redis.
- **Networking:**
  - private networking only for Postgres, Redis and clamav;
  - public domains only for `web` and `api`;
  - region EU West.
- **Deployment behaviour:**
  - a pre-deploy command runs `alembic upgrade head` as `app_owner`;
  - health checks on `/ready`.
- **Done when:** staging is live on the Railway domains.

**T23.2:**
- **Database roles:** create `app_owner` / `app_user` with RLS checks in staging; seed reference data (leave defaults, bank holidays, SOC data, rules v1 if approved, courses); **never seed demo data in production**.
- **Platform admin:** create the first Platform Admin with `python -m app.cli create-platform-admin --email ...`. It generates an invite link that is shown **only once**, in the terminal, to the owner.

**T23.3:** Cloudflare:
- DNS records (proxied) for `DOMAIN`, `www`, `api`, `admin` + staging equivalents, pointing to the Railway custom domains;
- SSL Full (strict); HSTS; WAF managed rules; rate-limit rule on `/api/v1/auth/*`; Turnstile site;
- R2 buckets (`brand-prod-files` EU jurisdiction, `brand-prod-backups`, `brand-staging-files`) with scoped API tokens;
- CORS on buckets limited to the app origins.

**T23.4:** Resend domain verification (SPF, DKIM, DMARC `p=quarantine` after testing); Stripe products and prices, webhook endpoints for staging (test mode) and production (live mode); Sentry projects (web, api) with scrubbing; uptime monitor on `/ready` and the homepage.

**T23.5:** GitHub Actions deploys: `deploy-staging.yml` on merge to `main` (after CI) and `deploy-production.yml` on a version tag with manual approval. Migrations run before the swap; automatic rollback on a failed health check.

**T23.6:** backups (nightly encrypted `pg_dump` to the R2 backups bucket via the worker, using the owner's age public key `BACKUP_AGE_PUBLIC_KEY`), a monthly restore-test job into a temporary database, and the runbooks (`restore.md`, `key-rotation.md`, `incident-response.md`, `rules-data-update.md`).

**T23.7:** staging acceptance: run the full E2E suite against staging, the ZAP baseline, Lighthouse, and the Stripe test-mode flows. Fix everything.

**T23.8:** production go-live: switch Stripe to live keys (the owner sets them), run the smoke tests, enable the uptime alerts, and submit the sitemap to search engines (owner action).

### Phase 24 — Launch checklist (Section 12) and handover
**T24.1:** complete every item in Section 12 and write `docs/handover.md` (how to operate, update rules data, rotate keys, restore backups, add a Platform Admin).

### Phase 25 — Later (do not start until the owner says so)
- US site and app (`us.DOMAIN`): Form I-9 register, E-Verify, state rules, PTO in hours, payroll export, US help centre, H-1B register, US tools/templates.
- Australia (`/au` waitlist page now; product in 2027).
- Native mobile wrapper (Capacitor) for clock in/out and notifications.
- Passkeys (WebAuthn) for login.
- SMS reporting reminders via calendar sync (Google/Microsoft).

---

## 10. Free calculators — specification (all run in the browser; rates from `web/rates/`)

**Rules for every calculator:**
- every figure comes from `web/rates/<area>.json` with `source_url`, `checked_on` and `valid_from`/`valid_to`;
- verify against GOV.UK/HMRC before release;
- support "tax year" selection where relevant;
- unit-test with official worked examples;
- show a sources table;
- nothing entered is stored or sent.

| # | Tool (route under `/resources/tools/`) | Inputs | Outputs |
|---|---|---|---|
| 1 | `right-to-work-october-2026-checker` | engagement type (employee / worker contract / individual sub-contractor / online matching service / other) + follow-ups | whether the extended RTW duty applies, what to do, records to keep (verify the rule) |
| 2 | `sponsor-licence-cost-calculator` | licence type (new/add route/renew), size (small/charity vs medium/large via turnover, assets, employees), route, inside/outside UK, CoS months slider, SOC, workers, adult and child dependants, speed (standard/priority), basis | licence fee, Immigration Skills Charge, CoS fee, visa fees, Immigration Health Surcharge, totals for employer vs worker, comparison of certificate lengths, the "14 days" note |
| 3 | `sponsor-reporting-deadline-calculator` | event type, event date, nation (bank holidays) | reportable?, deadline date (10/20 working days), days left, explanation |
| 4 | `skilled-worker-visa-checker` | SOC or job title (uses the same SOC data as 8.17, without AI), salary, hours, applicant situation, qualifiers | eligibility, minimum salary per option, dependants, English level |
| 5 | `ilr-citizenship-checker` | visa route (14 routes), start date, absences | ILR eligibility date, citizenship earliest date, timeline (verify current settlement rules) |
| 6 | `skilled-worker-ilr-salary-calculator` | SOC/job, hours | settlement-stage salary requirement |
| 7 | `holiday-entitlement-calculator` | mode (days per week / hours per week / part-year start-leave / irregular hours or part-year accrual 12.07%), relevant fields | entitlement in days or hours, with workings |
| 8 | `uk-take-home-salary-calculator` | region (England-NI / Scotland / Wales), salary, tax code (auto or custom), pension (method + %), student loan plan + postgrad, NI category, other jobs, benefits, other deductions | annual / monthly / weekly take-home with a breakdown table |
| 9 | `uk-employer-cost-calculator` | salary, age, employee type, pension rate + basis (qualifying earnings / full salary) | employer NI, pension, Apprenticeship Levy note, total cost |
| 10 | `uk-redundancy-pay-calculator` | jurisdiction (GB/NI), DOB, start date, redundancy date, weekly pay (or annual), status, reason | statutory redundancy pay with the capped week's pay and years |
| 11 | `uk-notice-pay-calculator` | jurisdiction, who gives notice, start date, notice date, employee status, contract notice, pay mode, arrangement (work/garden leave/PILON) | statutory vs contractual notice, notice pay, PILON and final pay notes |
| 12 | `uk-sick-pay-calculator` | jurisdiction, employee status, worker type, sickness start/end (or ongoing), part-day, qualifying days, earnings mode | SSP total and a week-by-week table (verify the current SSP rules: waiting days and lower earnings limit changes) |
| 13 | `uk-minimum-wage-underpayment-checker` | pay type, age, apprentice, pay frequency, period start, hours, pay, work costs, salary sacrifice, tips, accommodation offset | effective hourly rate vs NMW/NLW for the period, shortfall; rates table for current and past years |
| 14 | `risk-assessment-template` | organisation, site, country, employees, activity, assessor, dates, consulted, at-risk groups, reference/version, hazards (hazard, who, controls, further action, owner, due, status), acknowledgement | a downloadable risk assessment (PDF/DOCX), saved only in the browser |
| 15 | `sponsorship-job-checker` | see 8.17 (public version) | see 8.17 |

---

## 11. API catalogue (`https://api.DOMAIN/api/v1`)

**Conventions:**
- JSON in snake_case; cursor pagination `?cursor=&limit=` (max 100).
- Filters as query params; errors in the standard envelope; `402 PLAN_REQUIRED`; `403 FORBIDDEN`; 404 for cross-tenant ids.
- Every write needs CSRF; idempotency key header supported on POSTs that create payments or emails.
- The OpenAPI schema is the contract; regenerate the TS client after any change.

1. **Health:** `GET /health` · `GET /ready`
2. **Auth:**
   - Account: `POST /auth/signup` · `POST /auth/verify-email` · `POST /auth/resend-verification` · `POST /auth/login` · `POST /auth/logout` · `GET /auth/me`
   - Passwords: `POST /auth/forgot-password` · `POST /auth/reset-password` · `POST /auth/change-password`
   - MFA and step-up: `POST /auth/mfa/setup` · `POST /auth/mfa/verify` · `POST /auth/mfa/challenge` · `POST /auth/mfa/disable` · `POST /auth/mfa/recovery-codes` · `POST /auth/step-up`
   - Terms and invites: `POST /auth/accept-terms` · `GET /auth/invitations/{token}` · `POST /auth/invitations/{token}/accept`
   - Company switch: `POST /auth/switch-company`
3. **Company:** `GET/PATCH /companies/me` · `POST /companies/me/logo` · `GET /companies/lookup?number=` (Companies House) · CRUD `/locations` · `/departments` · `/designations` · `/companies/me/key-persons` · `/companies/me/compliance-documents` · `/bank-accounts` (+ `POST /bank-accounts/{id}/reveal`) · `/tax-codes` · `/payment-types` · `/pay-bands` · `/pay-schedules` · `GET/PUT /companies/me/working-pattern` · `GET/PUT /companies/me/trading-hours` · CRUD `/holidays` · `/holiday-types` · `GET /bank-holidays?region=&year=` · `GET /postcodes/{postcode}` (proxy to postcodes.io, cached)
4. **Users & RBAC:** `GET /users` · `POST /users/invite` · `POST /users/{id}/resend-invite` · `PATCH /users/{id}` · `POST /users/{id}/suspend` · `POST /users/{id}/reactivate` · `POST /users/{id}/link-employee` · `DELETE /users/{id}/link-employee` · `POST /users/{id}/reset-mfa` · `GET /roles` · `GET /roles/{role}/permissions` · `PUT /companies/me/mfa-policy`
5. **Files:** `POST /files` · `GET /files/{id}` · `GET /files/{id}/download-url`
6. **Employees:**
   - Records: `GET /employees` · `GET /employees/summary` · `POST /employees` · `GET/PATCH /employees/{id}` · `POST /employees/{id}/status` · `PATCH /employees/{id}/hire-date` · `POST /employees/{id}/photo` · `DELETE /employees/{id}` (guarded) · `GET /employees/{id}/record.pdf`
   - Sub-records, CRUD under `/employees/{id}/`: `addresses` · `emergency-contacts` · `responsibilities` · `previous-employment` · `education` · `training` · `memberships` · `documents`
   - History: `GET/POST /employees/{id}/assignments` · `GET/POST /employees/{id}/compensation`
   - Sensitive: `GET/PUT /employees/{id}/identity` · `POST /employees/{id}/identity/reveal` · `GET/PUT /employees/{id}/bank-details` · `POST /employees/{id}/bank-details/reveal`
   - Activity: `GET /employees/{id}/activity`
7. **Right to Work:** `GET/POST /employees/{id}/rtw-checks` · `GET/POST /candidates/{id}/rtw-checks` · `POST /rtw-checks/{id}/correct` · `GET /rtw-checks/{id}/evidence-sheet.pdf`
8. **Compliance:**
   - Hub: `GET /compliance/overview` · `GET /compliance/activity` · `GET /compliance/activity.csv`
   - Sponsor documents: `GET/POST /employees/{id}/sponsor-documents` · `POST /sponsor-documents/{id}/withdraw` · `GET /employees/{id}/sponsor-record.pdf` · `GET /compliance/sponsored-employees`
   - Changes: `GET /compliance/changes` · `POST /employees/{id}/changes` · `POST /changes/{id}/mark-reported` · CRUD `/compliance/org-changes`
   - Reminders: `GET /compliance/reminders` · `GET /compliance/reminders/due` · `GET /reminders/{id}` · `PATCH /reminders/{id}` (edit message) · `POST /reminders/{id}/send` · `POST /reminders/{id}/snooze`
   - Dossier: `GET /compliance/dossier`
9. **Leave:**
   - Settings and balances: `GET/PATCH /leave/settings` · CRUD `/leave/types` · `GET /leave-balances` · `GET /leave-balances/own` · `GET /employees/{id}/leave-balances` · `POST /employees/{id}/leave-balances/grant` · `/deduct` · `/set`
   - Requests: `GET /leave/requests` · `GET /leave/requests/own` · `POST /leave/requests` · `POST /leave/requests/own` · `POST /leave/requests/{id}/approve` · `/reject` · `/cancel` · `GET /leave/approvals/own`
   - Calendar and year end: `GET /leave/calendar?month=` · `POST /leave/year-end/preview` · `POST /leave/year-end/commit`
10. **Attendance:** `GET /attendance-records` · `GET /attendance-records/summary` · `GET /attendance-records/own` · `PUT /attendance-records` · `PUT /attendance/grid` · `GET /attendance/import/template.xlsx` · `.csv` · `POST /attendance/import/preview` · `POST /attendance/import/{id}/commit` · `GET /attendance/export.xlsx` · `.pdf` · `GET /attendance/absences?month=` · `POST /attendance/clock-in` · `POST /attendance/clock-out` · `GET /attendance/timesheets` · `POST /attendance/timesheets/{id}/approve`
11. **Rota:** CRUD `/rota/shift-types` · `/rota/late-policies` · `/rota/day-off-patterns` · `GET /rota/weeks/{week_start}` · CRUD `/rota/scheduled-shifts` · `POST /rota/weeks/{ws}/copy-last-week` · `/clear` · `/copy-day` · `/copy-employee-week` · `/clear-employee-week` · `/publish` · `GET /rota/weeks/{ws}/print.pdf` · `GET /rota/own`
12. **Work log:** `GET /work-log` · `GET/POST /work-log/own` · `PATCH /work-log/own/{id}` · `POST /work-log/{id}/correct` · `POST /work-log/{id}/remove`
13. **Documents & reports:** CRUD `/documents` · `POST /ai/letters/draft` · `POST /reports/{type}` (enqueue) · `GET /reports/jobs/{id}` (status + download URL)
14. **Policies:** `GET/POST /policies` · `GET/PATCH /policies/{id}` · `POST /policies/{id}/file` · `GET /policies/{id}/recipients` · `POST /policies/{id}/send` · `POST /policies/{id}/remind` · `POST /policies/{id}/new-version` · `GET /policies/{id}/acceptances` · `GET /policies/own` · `GET /policies/own/summary` · `POST /policies/{id}/accept`
15. **Recruitment:**
    - Requisitions, postings, candidates: CRUD `/requisitions` + `PATCH /requisitions/{id}/status` · CRUD `/postings` + `PATCH /postings/{id}/status` · CRUD `/candidates`
    - Applications: `GET/POST /applications` · `GET /applications/{id}` · `POST /applications/{id}/stage` · CRUD `/applications/{id}/interviews` · `POST /applications/{id}/offers` · `PATCH /offers/{id}` · `POST /applications/{id}/convert` · `GET /recruitment/summary`
16. **Org chart:** `GET /organogram` · CRUD `/organogram/levels` · `GET /organogram.pdf`
17. **Learning:** `GET /learning/courses` · `GET /learning/courses/{id}` · `POST /learning/assignments` · `GET /learning/assignments` · `GET /learning/assignments.xlsx` · `GET /learning/assignments/own` · `POST /learning/assignments/{id}/progress` · `POST /learning/assignments/{id}/quiz` · `POST /learning/assignments/{id}/complete` · `GET /certificates/{id}.pdf`
18. **Dashboard, search, notifications:** `GET /dashboard` · `GET /onboarding/checklist` · `POST /onboarding/checklist/dismiss` · `GET /search?q=` · `GET /notifications` · `POST /notifications/read-all` · `PATCH /notifications/{id}` · `GET/PUT /me/notification-preferences` · `GET/PUT /me/preferences`
19. **AI:** `POST /ai/ask` (SSE stream) · `GET /ai/suggestions`
20. **SOC checker:** `GET /soc/search?q=` · `POST /soc/match` · `GET /soc/{code}?date=&nation=` · `POST /soc/salary-check` · `POST /soc/resume-match` · `POST /soc/checks` · `GET /soc/checks` · `GET /soc/checks/{id}` · `POST /soc/checks/{id}/confirm` · `GET /soc/checks/{id}/report.pdf`
21. **Billing:** `GET /billing/subscription` · `POST /billing/checkout-session` · `POST /billing/portal-session` · `POST /billing/cancel` · `POST /webhooks/stripe` (no CSRF, signature-verified)
22. **Account lifecycle:** `POST /companies/me/export` · `GET /companies/me/exports/{id}` · `POST /companies/me/deletion-request` · `POST /companies/me/deletion-request/confirm` · `DELETE /companies/me/deletion-request`
23. **Audit:** `GET /audit-events` · `GET /audit-events.csv`
24. **Public (no auth, rate-limited, Turnstile on POST):** `POST /public/contact` · `GET /public/careers/{company_slug}` · `GET /public/postings/{company_slug}/{posting_slug}` · `POST /public/postings/{company_slug}/{posting_slug}/apply` · `GET /public/certificates/verify?ref=` · `GET /public/sponsors` · `GET /public/sponsors/{id}` · `GET /public/sponsors/stats` · `GET /public/register/publications` · `GET /public/register/changes/{date}` · `POST /public/sponsors/{id}/report` · `GET /public/soc/search?q=` · `GET /public/soc/{code}` · `POST /public/soc/salary-check`
25. **Super-admin (`/admin`, Platform Admin + MFA):**
    - Platform: `GET /admin/metrics` · `GET /admin/companies` · `GET /admin/companies/{id}` · `POST /admin/companies/{id}/suspend` · `/reactivate` · `/extend-plan` · `/notes` · `POST /admin/companies/{id}/impersonate` · `POST /admin/impersonation/{id}/end`
    - Billing and users: `GET /admin/subscriptions` · `POST /admin/refunds` · `GET /admin/deletion-requests` · `GET /admin/users?q=` · `POST /admin/users/{id}/lock` · `/unlock` · `/reset-mfa`
    - Rules: `GET /admin/rules/versions` · `POST /admin/rules/import` · `GET /admin/rules/versions/{id}/diff` · `POST /admin/rules/versions/{id}/publish` · `POST /admin/rules/versions/{id}/rollback`
    - Content: CRUD `/admin/courses` · `/admin/templates` · `/admin/guides` · `/admin/dossier-links` · `/admin/announcements` · `/admin/terms-versions` · `/admin/feature-flags`
    - Operations: `GET /admin/jobs` · `POST /admin/jobs/{id}/retry` · `GET /admin/register/status` · `POST /admin/register/run` · `GET /admin/contact-messages` · `PATCH /admin/contact-messages/{id}` · `GET /admin/audit-events`

**Background jobs (ARQ cron):**
- reminders_daily 06:00;
- rtw_status_daily 05:30;
- coc_deadlines_daily 05:45;
- leave_overdue/learning_overdue 06:15;
- register_ingest working days 10:00 and 16:00;
- bank_holidays_weekly Monday 03:00;
- rules_watch_daily 07:00;
- retention_purge_daily 02:00;
- backups_nightly 01:00;
- deletion_executor hourly;
- email_outbox every minute;
- stripe_reconcile daily 04:00;
- orphan_files_cleanup daily 03:30.
(All times Europe/London.)

---

## 12. Launch checklist (all must be ✓ before production go-live)
- [ ] Every task in Section 9 (Phases 0–24) is ticked in `PROGRESS.md`, with no open "Owner actions" except the ones the owner deferred.
- [ ] CI green; security workflow green; ZAP baseline has no high or medium findings.
- [ ] RBAC matrix test and tenant isolation tests cover 100% of endpoints.
- [ ] No secrets in repo history (`gitleaks detect --log-opts="--all"` clean), bundle or OpenAPI.
- [ ] Production uses live Stripe keys, separate R2 buckets, its own `FIELD_ENCRYPTION_KEYS`, `SESSION_SECRET`, `BLIND_INDEX_KEY` and webhook secret.
- [ ] Postgres and Redis are private-network only; the DB runtime user is `app_user` (no BYPASSRLS).
- [ ] Backups run, and a restore test succeeded in the last 7 days.
- [ ] Rules data v1 approved and published by the owner; TSL status for 2027 confirmed from GOV.UK.
- [ ] All rates in `web/rates/` verified, with `checked_on` within 30 days.
- [ ] Legal pages reviewed by a solicitor (owner) and the "DRAFT" labels removed by the owner's instruction.
- [ ] Resend domain verified with SPF, DKIM and DMARC; emails land in the inbox in Gmail/Outlook tests.
- [ ] Sentry receiving events with no PII; uptime monitor and alerts configured.
- [ ] Lighthouse ≥ 95 on marketing pages; axe 0 serious across the app.
- [ ] Design QA final screenshots reviewed by the owner.
- [ ] `docs/handover.md` complete.

---

## 13. Facts captured from the reference product (for parity checks)
- **Inspection readiness** checks: company profile complete; key personnel (AO, Key Contact, Level 1 User); company compliance documents; every current employee has an RTW check; every reportable change reported on time.
- **Reminders:** 90 / 60 / 30 days before Visa, Passport, DBS, EUSS and Other document expiry; reviewed before sending; the email doesn't name the document.
- **Reporting deadlines:** 10 working days (worker changes), 20 working days (organisation changes).
- **Uploads:** PDF/JPG/PNG/Word up to 25 MB.
- **Free plan:** never expires; paid unlocks writes; a lapsed plan becomes read-only; nothing is deleted.
- **14-day money-back guarantee**, cancelled from the Billing page with an automatic refund.
- **Account deletion:** 6-digit email code, deletion within 7 days, other admins notified, can be withdrawn, optional export first.
- **Two-step policy options:** optional / required for Company Admins / required for all.
- **Application stages** move forward one at a time; conversion needs an Accepted offer + Verified RTW.
- **Requisition** must be Open (approved) before a posting; External + Open postings get a public link; closing a posting disables the link.
- **Rota:** draft until published; quick-add shift chips; copy/clear at week, employee and day level; print.
- **Org chart** is built from Reporting Authority; hierarchy level is a label only.
- **Employee lifecycle:** Active / On leave / Leaver / Archived (reversible); permanent delete only for records created by mistake.
- **New starters' annual leave** is pro-rated automatically from hire date to leave-year end.
