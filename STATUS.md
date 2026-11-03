# STATUS
Updated: 2026-11-03 17:55, Europe/London    Agent: Codex    Branch: dev    Commit: d743206
State: IN PROGRESS

## Last completed
- T9.3 — clock/PWA, optional consented location and reviewed report timesheet approvals; API/browser/static pass

## Current task
- T9.4 — shift types, late policies and day off patterns
  - [x] Models/migration and validation schemas
  - [x] Scoped audited settings APIs and affected tests
  - [x] Settings tabs/forms and prerequisite empty states
  - [ ] Production browser/static checks
- Resume note: /rota/settings tabs/forms, shift suggestions/live paid hours/overnight breaks, scoped late/day-off forms, prerequisites/links and archive confirmation written. API34/migration7, Python mypy273, web types/lint/nav22 pass. Browser scenario ready for overnight shift + scoped rules + mobile axe + blocked archive and cleanup. Next production rota-settings browser then finish T9.4.

## Next tasks
- T9.5 — rota grid, publish, print and My Shifts
- T9.6 — Work Log
- Phase 9 gate — full suite/screenshots/green PR

## Health
- CI on dev: current head not rechecked; last confirmed gate all 12 green (41640316888). CI on main: not rechecked.
- Local checks run: T9.2 affected API31/browser4/static/web25 pass. T9.3 API39 + attendance27 + migration7/doc1, Python lint/format/mypy268, web type/lint/client/nav25 and production browser/setup2 (PWA/location/mobile axe) pass.

## Issues / suggestions
- Focused pytest invocation must group all tests/db paths before tests outside that directory; interleaving caused a missing database fixture, grouped rerun115 and notification alone1 pass.
- Remove dependency cooldown exceptions when due: brotli after 2026-11-05, certifi after 2026-11-06, pypdf after 2026-11-12.
- docs/audits/phase7.md absent from synced dev; F7.1–F7.7 queued findings were implemented and confirmed green in CI.

## Strategy / decisions taken
- T9.4: follow existing settings archive conventions; one active late policy/day-off pattern per department/designation/shift, overnight breaks validated within the shift. Deduction settings are stored configuration; no automatic payroll deduction is introduced.
- T9.3: weekly review uses a deterministic employee/week identifier for read-only projections; only approval writes a stamp with the reviewed record fingerprint. Changed records show review needed again. Location defaults off and requires employee consent per clock action; location/note text never enters audit events.
- T9.2: scanned import files use attendance_import ownership and require current company-wide attendance read even for their uploader after demotion. Preview/commit is all-or-nothing with per-row errors and stale-record checks. Grid may save worked status with unknown times/hours; it must not invent clock times. Workbook XML hardening follows https://openpyxl.readthedocs.io/en/stable/#security (defusedxml installed); parser limits and formula rejection follow next.
- T9.1: manual writes require full attendance.record.write; own-write is clock-only for T9.3. Employee row serializes upserts with leave booking. Leave-sync records cannot be overwritten. Company-local times become UTC instants; overnight clock-out rolls to next day, hours deduct unpaid break. Nonexistent wall times fail; repeated-hour entries require an explicit first/second occurrence. Audit excludes note text.
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
