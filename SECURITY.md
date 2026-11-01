# Security policy

This platform stores employee records, Right to Work evidence and sponsor-licence
documents for UK employers. We treat every report seriously.

## Reporting a vulnerability

**Report privately. Do not open a public issue, pull request or discussion.**

Use GitHub's private vulnerability reporting for this repository
(**Security → Report a vulnerability**). A dedicated security contact address and a
`/.well-known/security.txt` file are published once the production domain is set.

Please include:

- what you found and which component it affects (`web`, `api`, `worker`, infrastructure);
- the steps to reproduce it, and the impact you believe it has;
- the time you tested and the account or environment you used.

Please do not:

- access, change or delete data that is not yours, or test against another customer's account;
- run denial-of-service, spam or social-engineering attacks;
- include real personal data, real secrets or exploit code that touches production in your report.

### What you can expect

- An acknowledgement within 2 working days.
- A status update at least every 5 working days until the report is resolved.
- Credit in the fix notes if you want it.

## Scope

In scope: this repository, the deployed `web`, `api` and `worker` services, and their
configuration. Out of scope: findings that need a rooted device or physical access,
missing best-practice headers on third-party sites, and reports from automated scanners
with no demonstrated impact.

## Supported versions

Only the current `main` branch and the version running in production receive security fixes.

## How secrets are handled

The full rules are in `plan.md` section 4.1. In short:

- Secret values live **only** in the Railway environment variables for each environment,
  the owner's local `.env` (gitignored, test keys only), and the three GitHub Actions
  secrets named in `deployment-requirements.txt`.
- Secrets are never committed, logged, printed, pasted into chat, e-mails or tickets, or
  included in error messages. `.env.example` lists variable **names** only.
- The browser never receives a secret. Only the allow-listed `NEXT_PUBLIC_*` variables
  reach it, and CI fails the build if any other appears or if a secret prefix is found in
  the built bundle.
- `gitleaks` blocks secrets at commit time and in CI.
- Staging and production use different keys.

### If a secret is exposed

1. Revoke it in the provider's dashboard straight away.
2. Create a replacement and update it in Railway (and GitHub Actions if relevant).
3. Redeploy, then check the provider's logs for misuse.
4. Record the incident in the incident log.

The key-rotation runbook (`docs/runbooks/key-rotation.md`) is written alongside the
encryption code and the incident runbook with the deployment tasks.

## Security design

The security model (authentication, sessions, tenant isolation with Postgres row-level
security, RBAC, field-level encryption, audit log, file scanning, AI privacy rules, web
hardening and required security tests) is specified in `plan.md` sections 4.1 to 4.7. The
threat model is written to `docs/security.md` in the security hardening phase.
