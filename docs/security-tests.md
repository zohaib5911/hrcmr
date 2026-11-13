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

Run the complete API suite under the shared lock:

```sh
bash /home/zohaib/cmr_hr/.agent/bus.sh serial -- bash -c 'cd api && uv run pytest -q'
```

Run browser security checks (including the production build and bundle scan) under the same lock:

```sh
bash /home/zohaib/cmr_hr/.agent/bus.sh serial -- bash -c 'cd web && pnpm exec playwright test security-headers.spec.ts host-routing.spec.ts auth-flow.spec.ts --project=production'
```
