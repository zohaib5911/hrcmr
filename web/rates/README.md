# Verified calculator data

Checked directly against the linked GOV.UK / HMRC publications on **12 November 2026**.
Amounts are GBP, numeric rates in `values` are decimal fractions, and dates are ISO dates.
These files contain no user input and require no runtime network requests.
Government material is reused under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).

Each file carries `source_url`, `checked_on`, `valid_from`, `valid_to` and
`validity_basis`. `content` preserves official paragraphs, list items and table
cells for reviewing exceptions and worked examples. `values` supplies selected
numeric fields, inheriting the file's provenance and validity. Minimum-wage and
accommodation `periods` carry their own dates. `right-to-work.json` contains the
extracted text of the October employer-guide PDF in `content_text`.

## Validity and release checks

- `statutory_period`: the supported tax/rate year, with inclusive end dates.
- `commencement` / `guidance_edition`: the published reform or guidance start.
- `verification_snapshot_not_legal_commencement`: the source was checked on that
  date, not a claim about when the rule originally took effect. Supports an
  estimate as of that date, not historical reconstruction.
- `published_events_only`: only published events are supported. Check the chosen
  nation's date coverage before calculating a working-day deadline.
- A null `valid_to` means no confirmed expiry was captured. It does not guarantee
  that a rule or fee will remain unchanged. Reverify before release, including
  any amendments embedded in Immigration Rules that take effect later.

Never extrapolate an expired rate, silently substitute GB rules for NI, or assume
an unlisted figure is zero. If an input date, route, category or rule is not
covered, follow the task's **BLOCKED — needs verified figure** rule. Recheck the
primary source, add the missing dated evidence here, then implement it.

The wage page already publishes April 2027 figures; these are `announced` and
must not be used for a 2026 pay period. Plan 5 deductions start in 2026–27, so
the 2025–26 payroll file intentionally has no Plan 5 threshold.

## Calculator source map

| Tool                 | Files relative to this directory                                                                                                                                                                                                                                                                                                                            |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Right-to-work        | `right-to-work.json`: direct duty, extended liability, commencement conditions, retention and examples. Engagement type alone is insufficient.                                                                                                                                                                                                              |
| Sponsor licence cost | `licence.json`, `licence-duration.json`, `cos.json`, `skills-charge.json`, `sponsor-worker.json`, `visa-fees.json`, `health-visa-fees.json`, `ihs.json`, `visa-priority*.json`. Snapshot fees do not establish historical fees. SW 18.1 in `skilled-worker.json` supplies the extra 14 days after CoS end, subject to SW 18.1A; IHS depends on visa length. |
| Reporting deadlines  | `sponsor-duties.json` (C1–C4 and merger examples), `sponsor-worker.json`, `bank-holidays.json`. Event wording determines the trigger and deadline.                                                                                                                                                                                                          |
| Skilled Worker       | `skilled-worker.json`, `skilled-occupations.json`, `salary-list.json`, `english.json`. Preserve table IDs, SOC restrictions, transitions, hours bases and dependants rules.                                                                                                                                                                                 |
| ILR/citizenship      | `ilr-*.json`, `citizenship.json`, `citizenship-spouse.json`, `skilled-worker.json`. A projected date does not guarantee eligibility.                                                                                                                                                                                                                        |
| ILR salary           | `ilr-worker-salary.json`, `skilled-worker.json`, `skilled-occupations.json`, `salary-list.json`. Settlement exceptions differ from entry discounts.                                                                                                                                                                                                         |
| Holiday              | `holiday.json`, `holiday-accrual.json`. The 12.07% method is for qualifying irregular-hours/part-year leave years from April 2024; verify NI separately.                                                                                                                                                                                                    |
| Take-home salary     | `payroll-2025-26.json`, `payroll-2026-27.json`, `income-tax.json`, `pension.json`. PAYE tables retain their published band basis: distinguish gross income and taxable income after allowances. NI arrays retain published band order; thresholds retain actual weekly/monthly/yearly amounts.                                                              |
| Employer cost        | Payroll files and `pension.json`. Apply NI relief conditions and the chosen pension basis. Employment Allowance and Apprenticeship Levy are employer-wide, not per employee.                                                                                                                                                                                |
| Redundancy           | `redundancy-gb.json`, `redundancy-ni.json`. NI verifies the weekly cap only; verify NI eligibility/calculation rules separately.                                                                                                                                                                                                                            |
| Notice pay           | `notice-gb.json`, `notice-resignation.json`. Verify NI separately. Contract notice, PILON and final-pay treatment require their own conditions.                                                                                                                                                                                                             |
| Sick pay             | `sick-pay.json`, `sick-eligibility.json`, `sick-changes.json`, payroll files. Reform applies across the UK from 6 April 2026; check transitions for ongoing absences. Preserve HMRC daily-payment table upward rounding.                                                                                                                                    |
| Minimum wage         | `minimum-wage.json`, `accommodation.json`, `minimum-wage-calculation.json`. Historical age bands and apprenticeship rules matter. The calculation file is a guide index: verify its linked detailed guidance for pay-type arithmetic before implementing.                                                                                                   |
| Risk assessment      | No statutory monetary rates required.                                                                                                                                                                                                                                                                                                                       |

Settlement sources cover fourteen intended route choices: Skilled Worker, Health
and Care Worker, Minister of Religion, International Sportsperson, Scale-up,
Global Talent, Innovator Founder, UK Ancestry, BNO, long residence, partner/family,
refugee/humanitarian protection, legacy Tier 1 Entrepreneur and Tier 1 Investor.
The first four share the worker guide; Global Talent and legacy Tier 1 share the
business/investor guide and eligibility page. Do not treat all routes as a fixed
qualifying period. The continuous-residence appendix covers absence exceptions.

T15's SOC/rules importer remains the source of approved application rules data.
These public-tool captures do not publish or approve a rules version.

## Updating

1. Open `source_url`; check dates, tables, footnotes, exceptions and scheduled
   changes. Keep complete relevant sections. For PDFs compare extracted text
   against the document.
2. Update JSON, normalized fields and provenance together. Add a dated record
   rather than overwriting supported historical periods.
3. From `web/`, run `pnpm exec vitest run tests/unit/rates.test.ts`, lint and
   typecheck. Review the data diff against the official publication. Calculator
   blocks add official worked-example tests; integrity checks here do not
   certify future calculator implementations.
