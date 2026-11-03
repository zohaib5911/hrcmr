# STATUS
Updated: 2026-11-03 12:20, Europe/London    Agent: Codex    Branch: dev    Commit: f4a8c2c
State: IN PROGRESS

## Last completed
- T8.5 — audited reviewed carry-over, immutable closes and closed-year guards

## Current task
- Phase 8 gate — leave and holidays
  - [x] Full API/static checks
  - [ ] Full web/unit/browser checks
  - [ ] 390/1280 light/dark screenshots and visual review
  - [ ] Five-line summary, CI-green PR dev → main and merge
- Resume note: Full API590 pass/one generated-doc ordering failure fixed by sorting foreign-key reference notes; targeted doc1 pass. Static clean. Web full lint/types/contract pass; full unit776 pass/one stale bell-name expectation updated, targeted shell19 and guard scripts32 pass. Full browser407 pass/152 gated screenshots skipped/four stale shell assertions: profile Leave placeholder removed, built-route set updated, My leave/approvals headings/metadata normalized to sentence case. Next targeted four scenarios plus SCREENSHOTS=1 phase8-screenshots and visual review. Then five-line summary and green PR merge; continue T9.1.

## Next tasks
- Phase 8 gate
- T9.1 — attendance workspace, records and filters
- T9.2 — import, bulk entry and exports

## Health
- CI on dev: last run green (41610450677, audit fixes/T8.1); T8.2/T8.3 phase gate CI pending. CI on main: not rechecked.
- Local checks run: combined requests/ledger/RBAC/notifications/calculations 115 pass; notifications alone1 pass; API ruff/format/mypy (246 files), web typecheck and generated API contract pass. Prior T8.3 migration8 pass.

## Issues / suggestions
- Focused pytest invocation must group all tests/db paths before tests outside that directory; interleaving caused a missing database fixture, grouped rerun115 and notification alone1 pass.
- Remove dependency cooldown exceptions when due: brotli after 2026-11-05, certifi after 2026-11-06, pypdf after 2026-11-12.
- docs/audits/phase7.md absent from synced dev; F7.1–F7.7 queued findings were implemented and confirmed green in CI.

## Strategy / decisions taken
- T8.5: preview is read-only; commit only after year ends and pending requests resolve. Reconcile closing allowance, carry nonnegative remaining up to type limit (reasoned override may exceed limit up to remaining), expire positive source balances and freeze source-year mutations. Negative fixed-allowance debt requires a reviewed adjustment before closing; unbounded types retain usage history without treating it as allowance debt.
- T8.4: add missing leave.balance.read to plan/matrix so Company Admin/HR/Auditor can read company balances; existing own/reports remain scoped. Read projections combine immutable ledger with current managed allowance/calendar deltas; GET never writes. Manual actions reconcile and audit atomically.
- T8.2: balances are sums of signed immutable movements. Corrections append deltas; manual movements survive standard reconciliation. Employee row serializes writers; operation keys preserve retries, including no-op Set. Caller owns audit/commit transaction.
- Units are standard company days (weekly company hours / working weekdays). Personal shorter days reduce both entitlement and charge. Personal days inherit weekday hours unless overridden; new working weekdays use the company average. Exact fractions avoid rounding drift; entitlement/calendar totals round up once to 0.01 day.
- Regular-pattern entitlement uses inclusive employment calendar days; assignment end is exclusive. Monthly posts completed leave-months, with partial employment months pro-rata. Null allowances are not zero. Regular automatic calculation rejects zero-hours/casual assignments; reviewed manual grants are available. Sources/policy: data/leave/SOURCES.md.
- Explicit bank_holidays_included flag seeded true for Annual Leave and exposed in type settings. Regional non-working bank holidays and annual-deducting closures reserve scheduled personal days across the leave year, with overlaps charged once. Missing regional calendar year coverage fails explicitly. Reconciliation may record a negative balance to reflect corrected entitlements/reservations; manual deductions/sets obey the company negative-balance policy.
- T8.3: advisory minimum staffing warning when a proposed absence leaves nobody in the department; no blocking staffing rule is invented. Shift conflicts connect in Phase 9 once shifts exist. Request counter excludes all closures and non-working regional bank holidays, while ledger reserves annual deductions separately. Re-check snapshots before approval; changed dates/patterns require cancellation/resubmission.
- AI hidden without ANTHROPIC_API_KEY; Ask Mady deferred.

## Owner actions needed
- None. Existing non-blocking setup: protect main and enable private vulnerability reporting.
