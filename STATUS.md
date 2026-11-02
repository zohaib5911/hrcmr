# STATUS
Updated: 2026-11-02 15:30 (Europe/London)    Agent: Claude Code    Branch: dev    Commit: f87ecb4
State: IN PROGRESS

## Last completed
- T4.7 — Pay settings (committed). Fixes from the 2026-11-02 list are all in (client IP, lockout/new-device e-mails, dev-only samples, strict models, top-100k list, Cloudflare ranges job).

## Current task
- T4.7 done; Phase 4 gate passed, PR dev to main open (merge when CI is green)
  - [x] CI fixes: TRUSTED_PROXY_CIDRS in deployment-requirements, two Semgrep findings, rotation test
  - [x] e2e isolation: per-file company fixture (web/tests/support/fixtures.ts), fresh API DB each run, 1 local worker, test sign-ups use X-Real-IP
  - [x] Full e2e run: 375 passed, 0 failed
  - [x] Full API (384), web (755), guard (32): green
  - [x] Phase 4 summary written, gate ticked
  - [ ] PR dev -> main, merge when CI is green
- Resume note: if the e2e result is green, write the 5-line Phase 4 summary (format of Phase 3), tick "Phase 4 gate", open the PR. If red, fix the real failures only (rate-limit cascades are already fixed).

## Next tasks
- T5.1 (User Access list), T5.2, T5.3

## Health
- CI on dev: not yet run on the latest push    CI on main: red until the PR from dev merges (Web/Semgrep/API fixes are on dev)
- Local checks run: API 380 pass, web unit 755 pass, ruff/mypy/eslint/tsc clean (before the last edits)

## Issues / suggestions
- Remove the certifi exception after 2026-11-06
- Dependabot #5 open: merge when CI is green

## Strategy / decisions taken
- Relay mode; AI features hidden unless ANTHROPIC_API_KEY is set; Ask Mady deferred
- style-src-attr 'unsafe-inline' accepted (animation library)
- e2e: API server never reused locally; sign-ups send X-Real-IP (test API trusts 127.0.0.0/8) so the 5/hour sign-up limit stays on

## Owner actions needed
- None blocking. Protect `main` (require PR + CI passed); enable private vulnerability reporting.
