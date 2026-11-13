# Whole-project security scan — T25.3

Date: 2026-11-13. Reviewer: codex (BIG). Baseline: `38ceed56097a410237f28bcc529d1eb216bbe29c`.

Scope: plan §4 and §7, the threat model in `docs/security.md`, all registered API
routers and SQLAlchemy tables, production headers, dependencies and CI supply chain.
Severity follows `audit.md`: P0 security/tenant leakage or failing checks; P1 missing
required behaviour or security coverage; P2 non-blocking hardening. This is source
and local test evidence, not a deployed penetration test.

## Automated verification

Scans and exact results are being collected. Docker is unavailable inside the agent
jail; production image verification must be identified separately from local checks.

## Manual review

Router and table inventories, control evidence and findings follow in the completed report.

## Deployment limits

The HTTPS staging/WAF/origin-restriction and recovery checks in `leftover.md` remain
required before launch. The P25 gate reviews CSS/script changes from T25.2/T25.4–T25.6.
