# STATUS
Updated: 2026-11-03 11:55, Europe/London    Agent: Codex    Branch: dev    Commit: 71da003
State: HANDED OVER

## Last completed
- T8.3 — scoped requests/previews/LSA approvals, atomic ledger/attendance/notifications and security regressions

## Current task
- T8.3 — requests, conflicts, approvals and attendance synchronization
  - [x] Request and attendance models/migration
  - [x] Working-day counter and scoped request/approval API
  - [x] Booking ledger, attendance and transactional decision notifications
  - [x] Affected API/security/static checks
- Resume note: T8.3 complete. Start T8.4 with balance/calendar API and reasoned Grant/Deduct/Set endpoints around ledger.py; then /leave tabs, /my-leave, /my-approvals and employee Leave tab. Request endpoints already exist in request_router.py; UI shells in web/components/leave/home.tsx and employees/related-tabs.tsx. Follow plan.md Section 8 leave UX and Section 12 API paths.

## Next tasks
- T8.4 — leave workspaces and employee tab
- T8.5 — carry-over, then Phase 8 gate

## Health
- CI on dev: last run green (41610450677, audit fixes/T8.1); T8.2/T8.3 phase gate CI pending. CI on main: not rechecked.
- Local checks run: combined requests/ledger/RBAC/notifications/calculations 115 pass; notifications alone1 pass; API ruff/format/mypy (246 files), web typecheck and generated API contract pass. Prior T8.3 migration8 pass.

## Issues / suggestions
- Focused pytest invocation must group all tests/db paths before tests outside that directory; interleaving caused a missing database fixture, grouped rerun115 and notification alone1 pass.
- Remove dependency cooldown exceptions when due: brotli after 2026-11-05, certifi after 2026-11-06, pypdf after 2026-11-12.
- docs/audits/phase7.md absent from synced dev; F7.1–F7.7 queued findings were implemented and confirmed green in CI.

## Strategy / decisions taken
- T8.2: balances are sums of signed immutable movements. Corrections append deltas; manual movements survive standard reconciliation. Employee row serializes writers; operation keys preserve retries, including no-op Set. Caller owns audit/commit transaction.
- Units are standard company days (weekly company hours / working weekdays). Personal shorter days reduce both entitlement and charge. Personal days inherit weekday hours unless overridden; new working weekdays use the company average. Exact fractions avoid rounding drift; entitlement/calendar totals round up once to 0.01 day.
- Regular-pattern entitlement uses inclusive employment calendar days; assignment end is exclusive. Monthly posts completed leave-months, with partial employment months pro-rata. Null allowances are not zero. Regular automatic calculation rejects zero-hours/casual assignments; reviewed manual grants are available. Sources/policy: data/leave/SOURCES.md.
- Explicit bank_holidays_included flag seeded true for Annual Leave and exposed in type settings. Regional non-working bank holidays and annual-deducting closures reserve scheduled personal days across the leave year, with overlaps charged once. Missing regional calendar year coverage fails explicitly. Reconciliation may record a negative balance to reflect corrected entitlements/reservations; manual deductions/sets obey the company negative-balance policy.
- T8.3: advisory minimum staffing warning when a proposed absence leaves nobody in the department; no blocking staffing rule is invented. Shift conflicts connect in Phase 9 once shifts exist. Request counter excludes all closures and non-working regional bank holidays, while ledger reserves annual deductions separately. Re-check snapshots before approval; changed dates/patterns require cancellation/resubmission.
- AI hidden without ANTHROPIC_API_KEY; Ask Mady deferred.

## Owner actions needed
- None. Existing non-blocking setup: protect main and enable private vulnerability reporting.
