# STATUS
Updated: 2026-11-02 19:07 (Europe/London)    Agent: Codex    Branch: dev    Commit: 66f2533
State: IN PROGRESS

## Last completed
- T6.7 — Documents tab and masked employee inspection PDF

## Current task
- T6.7 — Documents tab and employee record PDF
  - [x] Requirements and baseline checks
  - [x] Documents API, scanned upload/download and isolation tests
  - [x] All/Payslips UI with explicit upload
  - [x] Masked multi-page PDF; browser journey passes
- Resume note: Start T6.8. Add Leave/Attendance/Learning shells linked to workspace routes; Activity uses existing audit events. Earlier CI 41504657493 still has only e2e pending, all other jobs green.

## Next tasks
- T6.8, Phase 6 gate, Phase 7

## Health
- CI on dev: 41504657493 pending e2e, other jobs green (7c99e60); current PDF/UI changes not yet in CI. CI on main: red (previous audit-export fix is on dev).
- Local checks run: T6.7 API/PDF/security 3 pass; Documents browser/setup 2 pass; ruff/mypy/eslint/tsc and production build pass. Earlier T6.5/T6.6 checks pass; no Phase 6 full suite yet.

## Issues / suggestions
- Remove certifi exception after 2026-11-06; Dependabot #5 pending green CI.

## Strategy / decisions taken
- PDF uses plan-specified WeasyPrint, lazy import, escaped template, blocked external resource fetcher and private/no-store response. Native libraries/fonts added to runtime and API/e2e CI. pypdf is test-only for text/masking checks.
- File APIs reuse scanned FileService; document-specific routes check target employee and document association. Employees may upload/read only their own files.
- Roles append in effective-date order; ended_at exclusive; hierarchy levels wait for Phase 9.
- Salary fetched only on Show salary; age-band preview uses dated verified GOV.UK rates, does not claim a pass with missing data.
- AI hidden without ANTHROPIC_API_KEY; Ask Mady deferred.

## Owner actions needed
- None blocking. Protect main and enable private vulnerability reporting.
