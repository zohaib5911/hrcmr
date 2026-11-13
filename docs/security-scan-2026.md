# Whole-project security scan — T25.3

Date: 2026-11-13. Reviewer: codex (BIG). Baseline: `38ceed56097a410237f28bcc529d1eb216bbe29c`.

Scope: plan §4 and §7, the threat model in `docs/security.md`, all registered API
routers and SQLAlchemy tables, production headers, dependencies and CI supply chain.
Severity follows `audit.md`: P0 security/tenant leakage or failing checks; P1 missing
required behaviour or security coverage; P2 non-blocking hardening. This is source
and local test evidence, not a deployed penetration test.

## Automated verification

Native versions match the CI pins. Results collected before the fixes:

| Gate | Local result |
| --- | --- |
| gitleaks 8.30.1, full history (`--log-opts=--all`, redacted) | 899 commits, 16.05 MB; zero leaks |
| Semgrep 1.180.0, all seven CI registry configurations | 1,190 files; zero findings, zero errors |
| pip-audit 2.10.1, frozen exported lock including development dependencies | No known vulnerabilities |
| pnpm production moderate+ and all dependencies high+ | Both report no known vulnerabilities |
| Trivy 0.75.0 config, MEDIUM/HIGH/CRITICAL | Zero findings in both Dockerfiles and scanned configuration |
| actionlint 1.7.12 | Exit 0, no findings |
| zizmor 1.30.1, offline, low+ | Three GitHub configuration files; no findings |

Docker reports no daemon inside the jail. API/web production image vulnerability
and secret scans cannot run locally; the unchanged mandatory `Image scan (api)`
and `Image scan (web)` PR jobs must pass before merge. They scan built image
archives at HIGH/CRITICAL, fixable vulnerabilities, and secrets. This report does
not claim an image pass or a deployed clean bill of health. See the T25.3 decision
in `.agent/decisions.md`.

## Manual review

Router and table inventories, control evidence and findings follow in the completed report.

## Deployment limits

The HTTPS staging/WAF/origin-restriction and recovery checks in `leftover.md` remain
required before launch. The P25 gate reviews CSS/script changes from T25.2/T25.4–T25.6.
