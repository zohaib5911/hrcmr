# Security scans and CSP verification

T21.3 checks repository hardening. Deployed staging verification is a separate,
required launch check tracked as L3 in `leftover.md`; it has not been run without
a configured HTTPS staging environment.

## Scan policy and reproduction

`.github/workflows/ci.yml` runs these gates on every PR to `dev` and `main`:

| Gate | What fails it |
| --- | --- |
| gitleaks | A secret anywhere in git history; values are redacted |
| pip-audit | An advisory in any locked Python dependency, including dev tools |
| pnpm audit | Production moderate+ or development high+ advisories |
| Semgrep | A finding in the configured Python, TypeScript, Next.js, Docker, Actions or OWASP rules |
| Trivy images | Fixable HIGH/CRITICAL vulnerabilities or secrets in the built API/web runtime images |
| Trivy config | MEDIUM/HIGH/CRITICAL Dockerfile misconfigurations |
| Web build | An unexpected public env name or secret pattern in the browser bundle |

All scanners are pinned in CI. `CI passed` requires every job to succeed. Do not
disable a gate, ignore an advisory or widen an allowlist to make a scan green.
Image gates cover production images, not the entire development Compose stack.
Unfixed image vulnerabilities and lower severities remain outside the blocking
policy; a passing image scan does not mean an image has no known vulnerabilities.

Local dependency checks (run from the indicated directory):

```sh
# api/
uv export --frozen --no-hashes --no-emit-project --output-file /tmp/hr-security-requirements.txt
uvx --exclude-newer "14 days" --from pip-audit==2.10.1 pip-audit \
  -r /tmp/hr-security-requirements.txt --disable-pip --no-deps --progress-spinner off

# web/: all severities, including development tools, for this hardening review
pnpm audit --audit-level low
```

Before T21.3, the complete JavaScript audit found two moderate development-tool
advisories: GHSA-3g3m-2fjr-6pw4 (`glob` via Lighthouse/Sentry bundler plugins) and
GHSA-g3hv-75wg-m249 (`minimatch` via the TypeScript ESLint parser). Scoped
`pnpm-workspace.yaml` overrides pin patched `glob` 14.0.2 and `minimatch` 11.0.1.
Both clear the 14-day release cooldown. Remove overrides when the parent packages
require fixed versions; verify lint, types, web tests and build after removal.

For the exact current commit, use its PR checks, not an earlier scan result:

```sh
gh pr checks <number>
```

The inherited baseline (AUDIT-4 round 3, PR #112, head
`a13206c7525a718308ed6cbce4e93b9f6492c2bb`) passed gitleaks, dependency audit,
Semgrep, both Trivy image scans and Dockerfile checks in
[CI run 43347210584](https://github.com/zohaib5911/hrcmr/actions/runs/43347210584).
That baseline is historical evidence only: it predates the patched JavaScript
lockfile. Docker is unavailable inside the agent jail, so current image scans
run in the new PR's CI, not locally.

T21.3 local verification on 2026-11-13: pip-audit and the complete pnpm audit
reported no known vulnerabilities; ESLint and TypeScript passed; all 1,466 web
unit tests (116 files) and 32 guard-script tests passed. The production build,
public-env allowlist and bundle scan passed while starting the browser test
servers; all 17 security-header/browser checks passed (including auth setup).
An initial probe run was 14 passed/3 failed because DevTools-inserted scripts
bypassed CSP; the corrected probes use parser-created scripts in intercepted
HTML, with the server's enforcing policy unchanged. No staging run is included.

## Local enforced CSP checks

`web/proxy.ts` already sends `Content-Security-Policy`, with a fresh nonce on
each response. `web/lib/security/csp.ts` keeps production scripts free of
`unsafe-inline` and `unsafe-eval`; the root layout renders dynamically. Keep
enforcement enabled by default. There is no client-controlled or environment
switch that downgrades it to report-only.

From `web/`, with the test service stack available:

```sh
bash /home/zohaib/cmr_hr/.agent/bus.sh serial -- \
  pnpm exec playwright test tests/e2e/security-headers.spec.ts --project production
```

This builds the production app and scans its browser bundle. Header tests cover
nonce uniqueness, nonce propagation, spoofed request headers and the other
security headers. Browser probes insert scripts with a missing, incorrect or
previous-response nonce. Each must raise an **enforced** `script-src-elem`
violation and never execute; a matching-nonce control must execute.
These probes work on the local HTTP host despite HTTPS upgrade blocking some
external resources; they do not prove full hydrated journeys on deployed HTTPS.

## HTTPS staging: report-only observation, then enforcement

Complete L3 once T23.1/T23.3 provide real staging hosts and configured test
accounts/Stripe/Turnstile. Use synthetic records and test provider keys only.

1. Record the deployed commit, HTTPS web/API/admin origins, date and browser.
   Check an unmodified response has an enforcing CSP and no shared HTML cache;
   check the edge preserves the nonce header and script nonce together.
2. In an isolated browser profile, use DevTools **local response-header
   overrides**, scoped to the staging document origins only. Move the response
   policy value from `Content-Security-Policy` to
   `Content-Security-Policy-Report-Only`. This changes only that browser's
   observations, not the server or the production default. Keep the original
   request-side nonce generation and returned HTML unchanged. Check the Network
   panel confirms the override; never override CSP on production.
3. Watch browser CSP console messages while exercising marketing, consent,
   signup/login/MFA/reset, tenant navigation, policy preview/upload, opted-in
   geolocation, Stripe checkout and Turnstile, and platform login/session/support
   on the actual admin host. Inspect all report-only violations; distinguish
   extension noise with the clean profile. Do not add broad wildcard script
   sources, `unsafe-inline` or `unsafe-eval` to suppress a finding. Report-only
   does not enforce `frame-ancestors` or HTTPS upgrade; verify these in step 4.
4. Remove **all** local overrides and reload with cache disabled. Confirm the
   Network panel shows the enforcing header, fresh matching nonces, no stale
   CDN HTML and no report-only replacement. Repeat the same flows and verify
   hydration/actions actually work over HTTPS on web and admin hosts. Repeat
   the inline-script negative/positive controls from the browser spec against
   the deployed policy, and confirm framing is denied.
5. Record results by route/flow and disposition, the commit and any fixes in a
   review artifact. Keep raw reports private if they include URLs, user data or
   tokens; commit only redacted summaries. No public CSP-report collector is
   installed by this task. If any required flow fails, L3 stays open and launch
   is blocked. Close L3 only with actual staging evidence.
