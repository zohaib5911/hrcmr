# STATUS
Updated: 2026-11-03 22:47, Europe/London    Agent: Codex    Branch: dev    Commit: 37f6f06
State: IN PROGRESS

## Last completed
- T9.6 — Work Log own/admin/API/forms complete; Work Log10+related26/migration7/static/browser2 pass

## Current task
- Phase 9 gate — full validation, design evidence and green PR
  - [x] Full API/static suite (once)
  - [x] Full web/unit/script/browser suite (sequentially)
  - [x] 390/1280 light/dark screenshots and visual review
  - [ ] Five-line phase summary, PR dev→main and green CI merge
- Resume note: All four screenshot variants pass across final run3+retry3; 76 images reviewed, axe/overflow clean. Five-line phase summary written. PR #15 opened; inspect current head checks and merge only after all CI checks green using gh pr merge 15 --merge --auto. Then sync dev and start T10.1 (baseline document/file/RBAC34 pass). Local full API658+corrected19, web777/scripts32, full browser413+retry8 and static/contract/build green.

## Next tasks
- T10.1 — company documents
- T10.2 — reports
- T10.3 — policies and sign-offs

## Health
- CI on dev: current head not rechecked; last confirmed gate all 12 green (41640316888). CI on main: not rechecked.
- Local checks run: T9.2 API31/browser4/static; T9.3 API39+attendance27/migration7/doc1/static/web25/browser2; T9.4 API34/migration7/static/web22/browser2; T9.5 affected61+isolated rota9/clock-email12/migration7/static/web22/browser3; T9.6 Work Log10+related26/migration7/mypy288/static/web22/browser2 — pass.

## Issues / suggestions
- Never run database pytest alongside Playwright: both provision shared PostgreSQL roles with random passwords, so concurrent setup causes app_owner authentication failures. Run them sequentially.
- Focused pytest invocation must group all tests/db paths before tests outside that directory; interleaving caused a missing database fixture, grouped rerun115 and notification alone1 pass.
- Remove dependency cooldown exceptions when due: brotli after 2026-11-05, certifi after 2026-11-06, pypdf after 2026-11-12.
- docs/audits/phase7.md absent from synced dev; F7.1–F7.7 queued findings were implemented and confirmed green in CI.

## Strategy / decisions taken
- T9.6: work log duration uses the entered HH:MM interval, wrapping overnight. Own edit eligibility uses company-local work date. Responsibility wording is snapshotted; first admin correction retains the complete original, later changes remain audited. Free entry text stays out of audit events. Revision checks prevent overwriting intervening edits.
- T9.5: preserve last published shifts in a weekly snapshot while draft edits change current rows; manager publication merges only their reports and preserves other employees. Version checks prevent stale destructive actions. Times are UTC instants derived from explicit company-local wall times/fold choices.
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
