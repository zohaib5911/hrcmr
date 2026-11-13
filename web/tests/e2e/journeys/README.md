# Top 25 user journeys

Run `pnpm test:journeys` from `web/` (or `pnpm test:e2e` to include them in the full suite).
The existing E2E wrapper takes the shared agent lock locally. CI discovers these specs through
`playwright.config.ts`; each spec covers one independently runnable journey (leave settings also retains four theme/viewport
accessibility checks). Existing component
and security specs remain outside this folder. Moving existing workflows here avoids running
copies of the same tests in CI.

For one journey, use `pnpm test:e2e tests/e2e/journeys/careers.spec.ts --project=production`.
Playwright combines multiple positional file filters with OR, so adding a filename to
`test:journeys` still selects the whole journey directory.

The Playwright setup creates its own throwaway API database, Redis database and signed-in account.
Each journey gets a separate company; role/visitor transitions use separate browser contexts.
Required local services are Postgres test, Redis, Mailpit, RustFS and ClamAV (see the root compose file).

| # | Spec | Journey and outcomes |
| --- | --- | --- |
| 1 | auth-flow | Signup, email confirmation, MFA sign-in/recovery and password reset |
| 2 | subscription-onboarding | Free signup → blocked write → paid activation → first employee → scanned RTW → send follow-up reminder |
| 3 | rtw | Conditional checks, explicit evidence selection, masked share code, correction and directory filters |
| 4 | reminders | Draft, snooze, send once, sender history and employee received message |
| 5 | leave-workspace | Request, approve, calendar, balance adjustments and own cancellation |
| 6 | rota-workspace | Plan, publish, My Shifts, copy and confirmed clearing |
| 7 | requisition-approval | Create, approve and confirmed cancellation |
| 8 | candidate-rtw | Add candidate and record a check; missing evidence prevents verified status |
| 9 | candidate-application | Apply an existing candidate, shortlist and inspect the pipeline |
| 10 | careers | Open public posting → apply → interview/calendar/outcome → accepted offer → verified RTW → convert once; closed/missing links refused |
| 11 | policies | Send policy, employee signature, admin receipt and employee forbidden admin view |
| 12 | learning-player | Assign, saved progress, failed checks, pass, completion, certificate download and signed-out verification |
| 13 | sponsorship-checker | SOC search, confirmation and PDF report |
| 14 | account-deletion | Request, email code, seven-day schedule and withdrawal |
| 15 | attendance-clock | Home clock-in, location consent, clock-out and manager approval |
| 16 | attendance-batches | Invalid import preview, corrected import, bulk changes and export |
| 17 | work-log | Daily record, explicit edit, reasoned correction and retained history |
| 18 | company-documents | Real scanned upload, filter, download, edit and retained archive |
| 19 | sponsor-documents | Explicit saves, versions, renewals and reasoned withdrawal |
| 20 | reports | Queue worker-generated exports, download and persisted recent jobs |
| 21 | organogram | Search, inspector, list and PDF agreement |
| 22 | leave-year-end | Preview carry-over, exception and committed year-end |
| 23 | leave-settings | Verified defaults, saved settings and leave-type lifecycle |
| 24 | rota-settings | Overnight shifts, late policy and regular days off |
| 25 | dashboard | Permission-aware cards and persisted checklist dismissal |

## External boundaries

- Stripe checkout is external: `subscription-onboarding` uses the existing test-only paid-plan route
  after real free signup, verifies the same session gains writes, and checks Billing reflects it.
  Stripe signature/webhook/idempotency behaviour is covered by API billing tests; a real hosted
  checkout still needs configured deployment credentials.
- Signup and deletion email codes come from Mailpit. Public careers uses the test server's Turnstile
  configuration. SOC/rules and courses use the E2E server's fixed reference fixtures.
- `subscription-onboarding`, `careers`, `company-documents` and `policies` use real scanned files.
  The older `rtw` and `sponsor-documents` journeys retain their document-picker mocks to test explicit
  selection separately. Candidate RTW's compact form has no evidence picker; `careers` binds real
  scanned evidence through the authenticated API before browser conversion, including refusal
  without evidence and refusal of a duplicate conversion.
- API requests set up prerequisite records where UI creation is exercised by another journey.
  These tests do not execute irreversible account purging or charge a real payment method.
