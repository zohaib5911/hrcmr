# STATUS
Updated: 2026-11-02 18:56 (Europe/London)    Agent: Codex    Branch: dev    Commit: b512566
State: IN PROGRESS

## Last completed
- T6.6 — Salary: hidden until shown, permission-gated history and explicit add-record sheet with age-band minimum-wage preview

## Current task
- T6.7 — Documents tab and employee record PDF
  - [x] Read requirements, baseline checks; installed plan-specified WeasyPrint with runtime/CI libraries
  - [x] Documents API and tests (3 pass including parsed PDF/security tests)
  - [ ] Documents UI (All/Payslips, upload category, scan status, short-lived download)
  - [ ] Full masked employee PDF and browser verification
- Resume note: backend complete; build documents-tab.tsx and Print record action, then browser check. Previous: implement document_router.py and PDF service; WeasyPrint must import lazily so OpenAPI export needs no native libraries. Previous: Check CI 41504657493 first (runs 7c99e60, includes all backend changes and T6.4 CI fix; salary UI landed later in f7199b9). If red fix it first. Then T6.7; EmployeeDocument already exists. Follow api/app/modules/files/service.py and companies/compliance_documents.py for safe upload/download. No PDF library currently in pyproject.toml. Salary UI/browser checks pass locally.

## Next tasks
- T6.7, T6.8, Phase 6 gate (full suite once, 390/1280 screenshots, PR dev to main), then Phase 7

## Health
- CI on dev: pending 41504657493 on 7c99e60; API and all other checks green; only e2e pending. Earlier ca40751 failed only generated data-model drift, fixed in 889e1d8; all its other jobs passed.
- CI on main: red (41436835247; previous relay reports audit-export fix already on dev).
- Local checks run: Employment affected API/reporting/doc 26 pass, employee web unit 13 pass, Employment browser/setup 2 pass; Salary API/unit 10 pass, Salary browser/setup 2 pass. Ruff/mypy/eslint/tsc, generated types and production builds pass. No phase gate full-suite run yet.

## Issues / suggestions
- Remove certifi exception after 2026-11-06; Dependabot #5 pending green CI.

## Strategy / decisions taken
- Roles append in increasing effective-date order; ended_at is exclusive. Employee list/profile and reporting permissions use today's effective role, including scheduled changes.
- Org-assignment write permission gates Employment edits; profile read scope gates views. API supplies role labels to readers without company-settings access.
- Hierarchy selection waits for the Phase 9 organogram table (model comment); arbitrary IDs refused meanwhile.
- Salary is absent from server profile payload; fetched only by Show salary. Compensation write gates adding/checking salary.
- Wage preview compares basic hourly pay to the age-band rate on effective_from; unknown age/hours/rates never claims a pass. Apprentice eligibility, actual hours and deductions need separate assessment. Rates for April 2024–March 2028 verified at https://www.gov.uk/national-minimum-wage-rates on 2026-11-02; code: minimum_wage.py.
- Personal identity/bank reveal requires step-up and audit. AI features hidden without ANTHROPIC_API_KEY; Ask Mady deferred.

## Owner actions needed
- None blocking. Protect main and enable private vulnerability reporting.
