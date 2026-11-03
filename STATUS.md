# STATUS
Updated: 2026-11-03 13:34, Europe/London    Agent: Codex    Branch: dev    Commit: dade98e
State: IN PROGRESS

## Last completed
- T9.1 — attendance APIs, manual record sheet, KPIs/ranges/filters and employee history

## Current task
- T9.1 — attendance records, record sheet and workspace
  - [x] Scoped list/own/summary APIs and validated audited upsert
  - [x] API validation, scopes, concurrency and leave-sync safeguards
  - [x] Day/week/month/custom workspace, KPIs, filters and record sheet
  - [x] Employee Attendance tab and affected browser/static checks
- Resume note: T9.1 complete: API36/baseline47/browser5 including mobile axe and static/client pass. Start T9.2 attendance import model/file-purpose integration, XLSX/CSV template/preview/commit, bulk grid, exports and monthly absences report.

## Next tasks
- T9.1 — attendance workspace, records and filters
- T9.2 — import, bulk entry and exports
- T9.3 — clock in/out and timesheet approvals

## Health
- CI on dev: Phase 8 all 12 green (41640316888). CI on main: post-merge run pending/not rechecked.
- Local checks run: API590 plus corrected generated-doc1/affected55 pass; web776 plus corrected shell19/nav22, guard scripts32 pass; browser407 plus four corrected cases and screenshot/setup5 pass. Python/web static, production build and generated contract clean. 48 screenshots saved/reviewed.

## Issues / suggestions
- Focused pytest invocation must group all tests/db paths before tests outside that directory; interleaving caused a missing database fixture, grouped rerun115 and notification alone1 pass.
- Remove dependency cooldown exceptions when due: brotli after 2026-11-05, certifi after 2026-11-06, pypdf after 2026-11-12.
- docs/audits/phase7.md absent from synced dev; F7.1–F7.7 queued findings were implemented and confirmed green in CI.

## Strategy / decisions taken
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
