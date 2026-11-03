# STATUS
Updated: 2026-11-03 09:54, Europe/London    Agent: Codex    Branch: dev    Commit: e8d2c3a
State: IN PROGRESS

## Last completed
- T8.2 — immutable tenant ledger, balance view, pro-rata/pattern/calendar computation and serialized services

## Current task
- T8.2 — complete
  - [x] Prior audit/T8.1 implementation CI green: 41610450677 at 0d3b86d, all twelve checks
  - [x] Pure calculation suite; exact arithmetic, leave years, starters/leavers, personal hours/history
  - [x] Append-only ledger, composite tenant references, caller-scoped balance view, migration round-trip
  - [x] Manual grant/deduct/set with reason/retry keys; idempotent standard/calendar reconciliation
  - [x] Affected tests, static checks and leave-settings production browser flow
- Resume note: Start T8.3 requests/conflicts/approvals and attendance synchronization. Ledger services in api/app/modules/leave/ledger.py do not commit; endpoint callers must audit and commit in one transaction. Reads do not implicitly grant. No T8.3 code yet. Balance endpoints and workspaces remain T8.4.

## Next tasks
- T8.3 — requests, working-days counter, conflicts, approvals, notifications, attendance sync
- T8.4 — leave workspaces and employee tab
- T8.5 — carry-over, then Phase 8 gate

## Health
- CI on dev: pre-T8.2 implementation green (41610450677); T8.2 has affected local checks, phase CI gate pending. CI on main: not rechecked.
- Local checks run: calculation28, ledger20, DB guards/isolation31, migration/settings17, browser/setup6 pass; API ruff/format/mypy (239 files), web types/targeted ESLint and generated API contract pass.

## Issues / suggestions
- Remove dependency cooldown exceptions when due: brotli after 2026-11-05, certifi after 2026-11-06, pypdf after 2026-11-12.
- docs/audits/phase7.md absent from synced dev; F7.1–F7.7 queued findings were implemented and confirmed green in CI.

## Strategy / decisions taken
- T8.2: balances are sums of signed immutable movements. Corrections append deltas; manual movements survive standard reconciliation. Employee row serializes writers; operation keys preserve retries, including no-op Set. Caller owns audit/commit transaction.
- Units are standard company days (weekly company hours / working weekdays). Personal shorter days reduce both entitlement and charge. Personal days inherit weekday hours unless overridden; new working weekdays use the company average. Exact fractions avoid rounding drift; entitlement/calendar totals round up once to 0.01 day.
- Regular-pattern entitlement uses inclusive employment calendar days; assignment end is exclusive. Monthly posts completed leave-months, with partial employment months pro-rata. Null allowances are not zero. Regular automatic calculation rejects zero-hours/casual assignments; reviewed manual grants are available. Sources/policy: data/leave/SOURCES.md.
- Explicit bank_holidays_included flag seeded true for Annual Leave and exposed in type settings. Regional non-working bank holidays and annual-deducting closures reserve scheduled personal days across the leave year, with overlaps charged once. Missing regional calendar year coverage fails explicitly. Reconciliation may record a negative balance to reflect corrected entitlements/reservations; manual deductions/sets obey the company negative-balance policy.
- AI hidden without ANTHROPIC_API_KEY; Ask Mady deferred.

## Owner actions needed
- None for T8.3. Existing non-blocking setup: protect main and enable private vulnerability reporting.
