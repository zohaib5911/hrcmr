# STATUS (snapshot — live state is `bash .agent/bus.sh status`)
Updated: 2026-11-12 09:05 (Europe/London)    Agent: Claude Code (Opus 5.5, BIG)    Branch: dev
State: HANDED OVER — audit fixes ready (AUDIT-3 round 2: 1 P0 / 4 P1 / 1 P2).

## Last completed
- Parallel-mode setup: `.agent/bus.sh` (claims, messages, journal, decisions, serial test lock), `.agent/next.sh` (per-agent, deps-aware),
  `.agent/prs.sh` (merges green task PRs and ticks them), `.agent/run.sh` + `.agent/start.sh` (auto-restart after usage limits),
  `.agent/deps.txt`, `.agent/decisions.md`; CI now runs on PRs to `dev`.
- C3.1.4–C3.1.10 unblocked: e2e decision in `.agent/decisions.md`.
- Before this: AUDIT-3 fixes C3.1.1–3 and C3.1.11–16 (see git log 9 Nov).

## Ready in parallel now
- SMALL: C3.1.4 (then C3.1.5–C3.1.9 in parallel, then C3.1.10), T18.1, T18.2, T18.4, T19.16, T19.17, T20.1.
- BIG: T19.1 (unlocks the 13 calculators T19.2 → T19.3–T19.15).

## Health
- CI on dev: the 9 Nov fix commits have not run in CI yet; the first task PR to dev will run them. CI on main: green (PR #26).

## Issues / suggestions (carried over)
- Test-order issue: run tests/test_architecture.py or tests/test_openapi.py separately from tests/db.
- Route prefixes are mixed: `/platform/*` and the older `/admin/*`. (T16.6) breadcrumb "Company / Company". (T16.3) Stripe API version not pinned. (T16.2) a lapsed annual plan still says "annual" in /auth/me.
- The billing page's cancel-at-period-end copy and the comp alert have unit tests only.

## Owner actions needed
- leftover.md L1: Stripe test keys (before Phase 23). Manual check: admin-host session start with an MFA-enabled platform admin.
