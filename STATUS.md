# STATUS
Updated: 2026-11-03 09:54, Europe/London    Agent: Codex    Branch: dev    Commit: 6d51e12
State: IN PROGRESS

## Last completed
- T8.2 — immutable tenant ledger, balance view, pro-rata/pattern/calendar computation and serialized services

## Current task
- T8.3 — requests, conflicts, approvals and attendance synchronization
  - [ ] Request and attendance models/migration
  - [ ] Working-day counter and scoped request/approval API
  - [ ] Booking ledger, attendance and transactional decision notifications
  - [ ] Affected API/security/static checks
- Resume note: Starting T8.3. Reuse ledger helpers with callers auditing/committing. No request code yet. Balance workspaces remain T8.4; rota entities arrive in Phase 9, when shift clashes can be evaluated.

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
