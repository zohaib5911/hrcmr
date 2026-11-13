# Security test coverage

T21.1 covers plan §4.7. Run commands from the repository root unless stated otherwise.

## Endpoint authorization

`api/tests/fixtures/endpoint_permissions.json` is the reviewed method/path inventory: 436 endpoint-method pairs, including 393 permission-bearing pairs (350 tenant and 43 platform), and 43 explicit exceptions. Review changes to this fixture as authorization policy changes. Do not regenerate it blindly to fix a failure.

- `test_endpoint_security.py` compares the live dependency graph to the inventory. Added or removed routes, changed permissions, and removed guards fail. Exceptions are exact method/path entries; adding an account or public route cannot inherit a prefix exemption.
- `test_rbac_enforcement.py` resolves the real dependency graph for all six tenant roles against all 393 permission-bearing pairs (2,358 combinations). It checks denial codes or admitted scopes against the separately tested plan role matrix, and checks that admitted access carries the caller's company ID.
- `test_endpoint_security.py` denies anonymous callers on all 393 guarded pairs and admits both platform levels on all 43 platform guard pairs (86 combinations). Platform permissions also cover course and SOC editors outside `/platform/`.
- Account flows (22), public endpoints (18), health probes (2), and the Stripe webhook (1) use their own checks rather than tenant permissions. Their exact routes are inventoried; behavior is exercised in the suites below.

The matrix resolves guards without invoking business handlers. It does not treat missing body/path validation as an authorization pass. Resource ownership, owner-only platform actions, step-up requirements, and changes to business records are exercised through HTTP in the module tests, including `test_platform_admin.py`, `test_platform_billing.py`, and `test_support_mode.py`.

## Plan §4.7 checks

| Requirement | Coverage |
| --- | --- |
| Tenant isolation | Module HTTP tests in `api/tests/db/`, plus `test_rls_isolation.py` and `test_tenant_session.py`; the matrix verifies tenant context across guarded routes. |
| RBAC | Endpoint inventory, all-role guard matrix, platform and anonymous matrices, and the plan grants in `test_rbac_matrix.py`. |
| Authentication | `test_auth_flows.py`, `test_auth_endpoints.py`, `test_user_access.py`, and platform/support tests cover lockout, rotation, CSRF, policy MFA, step-up and invitation expiry. |
| Uploads | `test_files.py` rejects oversize, mismatched magic bytes, EICAR and scanner failures. Module upload tests also check resource ownership. |
| Secret leaks | `test_openapi.py`; `node --test scripts/tests/*.test.mjs`; `node scripts/scan-bundle.mjs` (also runs after every web build). |
| Webhook signature | `test_stripe.py` and `test_billing.py`: invalid signatures, replay protection and unchanged state after rejection. |
| Staging baseline | `.github/workflows/security.yml` runs OWASP ZAP against an HTTPS staging host only. No `STAGING_URL` repository variable exists at this check, so no staging scan was run. Deployment must configure it and run the workflow; this is not a passing scan result. |

## Pen-test style checks (T21.4)

| Check | Coverage |
| --- | --- |
| IDOR on every `{id}` route | `api/tests/db/test_pentest_idor.py`: company A's admin, after step-up, calls every tenant route whose path params are ids (from the reviewed inventory) with company B's real employee, department, designation, holiday type and membership ids, and unknown ids elsewhere. Every call is refused (403/404/409/410/422/429), none echoes B's data, and B's rows are unchanged. Platform routes cross companies by design and are covered by `test_platform_*`. |
| Mass assignment | `api/tests/test_pentest.py` walks every request body model, nested models included (over 100), and requires `extra="forbid"`; `test_openapi.py` checks the top-level bodies in the published schema. |
| SSRF | `test_pentest.py` pins the modules that may make outbound requests and the only host each names (GOV.UK, postcodes.io, Companies House, plus the Stripe, Resend, Anthropic, Cloudflare and HIBP APIs; ONS place names are loaded from a file by the CLI, never fetched). User input never becomes a URL: postcodes and company numbers are normalised to a fixed pattern first. The register ingest re-checks every redirect against its host allowlist; the rules watch now refuses any redirect off `https://www.gov.uk` (it previously followed redirects anywhere). |
| Path traversal | Storage keys are server-made UUIDs. `test_pentest.py` checks that upload and export-zip names can never contain a path separator, NUL or a leading dot. |
| Open redirects | `safeNextPath` is the only `next=` sink (platform session start); `web/lib/security/pentest.test.ts` resolves hostile values against the admin origin and requires the same origin. Export downloads redirect only to server-made presigned links; Stripe return URLs are built from `WEB_ORIGIN`. |
| Rate limits and lockout | `test_auth_flows.py` and `test_auth_endpoints.py` (lockout growth, unknown-address parity); public forms in `test_contact_public.py`, `test_careers.py`, `test_soc_public.py` and `test_register_public.py`. |
| Session fixation | `test_auth_flows.py`: signing in, rotating and signing out each issue a new token, and rotation drops step-up. |
| Clickjacking | The API now sends `Content-Security-Policy: frame-ancestors 'none'`, `X-Frame-Options: DENY`, `nosniff` and `Referrer-Policy: no-referrer` on every response that sets no policy of its own (the policy viewer keeps its `frame-ancestors` for the web origin); `test_pentest.py`. The web app's frame protection is in `security-headers.spec.ts`. |
| XSS | `pentest.test.ts`: `dangerouslySetInnerHTML` only in the two reviewed files (brand accent CSS from repository config, and escaped JSON-LD tested in `seo.test.ts`); no `innerHTML`, `insertAdjacentHTML`, `document.write`, `eval` or `new Function`. MDX is compiled from repository content at build time; no user Markdown is rendered. Email templates escape every value. |
| SQL injection | `test_pentest.py`: every `text()` argument in the app is a string literal with bound parameters; the only run-time SQL is the provisioner's DDL from code constants. |

The shared test Redis (database 15) is flushed by every API fixture. Run the IDOR sweep alone, or with `TEST_REDIS_URL` set to a private database number, when another agent is running tests.

Run the complete API suite under the shared lock:

```sh
bash /home/zohaib/cmr_hr/.agent/bus.sh serial -- bash -c 'cd api && uv run pytest -q'
```

Run browser security checks (including the production build and bundle scan) under the same lock:

```sh
bash /home/zohaib/cmr_hr/.agent/bus.sh serial -- bash -c 'cd web && pnpm exec playwright test security-headers.spec.ts host-routing.spec.ts auth-flow.spec.ts --project=production'
```

## Validation on 2026-11-13

- Full API suite: **1,385 passed**, no failures or skips (458.96 s).
- Targeted endpoint/RBAC suite before the full run: **26 passed**.
- Production Playwright authentication, host routing and security headers: **28 passed** (40.3 s), including setup; production build and bundle scan completed as part of server startup.
- Scanner/public environment tests: **32 passed**; bundle scanner clean.
- Ruff lint and formatting clean; mypy clean across **493 source files**, with the subsequently tightened matrix files checked again.
- ZAP staging baseline: **not run**, because no staging target is configured.
