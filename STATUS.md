# STATUS
Updated: 2026-11-03 17:27, Europe/London    Agent: Codex    Branch: dev    Commit: b06a3d2
State: IN PROGRESS

## Last completed
- T9.1 — attendance APIs, manual record sheet, KPIs/ranges/filters and employee history

## Current task
- T9.2 — attendance import, bulk entry, exports and absences
  - [x] Import schema/file purpose, workbook dependency and shared row service
  - [x] XLSX/CSV templates and preview/commit with row errors
  - [x] Bulk grid API, XLSX/PDF exports and monthly absences
  - [x] Import/bulk/report UI and toolbar downloads
  - [ ] Affected API/browser checks
- Resume note: Affected API31 and static checks pass. Browser found file-picker exact-label mismatch and toolbar missing group role; corrected both. Import/commit/bulk flow reaches mobile axe: translucent tab-bar secondary labels fail contrast over the grid; use primary labels. Mobile grid now passes axe; absence assertion corrected for responsive card list. Rerun attendance-batches only; manual attendance browser2 already green. No full suite/screenshots until Phase 9 gate.

## Next tasks
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
