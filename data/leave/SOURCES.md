# Leave defaults

Checked 2026-11-03 against the GOV.UK pages below. Summaries are original and kept with each
company's seeded type as `source_url`, `checked_on` and `rule_text`. Migration 0021 freezes the
initial snapshot; signup uses `app/modules/leave/reference.py`. Editing a company policy keeps
its seed reference, which describes the original summary rather than certifying custom policy.

The paid flag means paid provision exists subject to eligibility, not full salary for the entire
leave. These are configuration defaults; payroll and statutory eligibility are not calculated.
Annual leave includes bank holidays. Five carry-over days is company policy, not a statutory cap;
protected family-leave, sickness and employer-failure exceptions can require more carry-over.
Unpaid Leave is an agreed company-policy category, rather than a separate statutory allowance.
GOV.UK notes regional differences, including Northern Ireland; follow the linked guidance.

| Default | Verified source |
|---|---|
| Annual Leave | [Annual Leave](https://www.gov.uk/holiday-entitlement-rights) |
| Sick Leave | [Sick Leave](https://www.gov.uk/guidance/sickness-absences-that-start-before-and-end-on-or-after-6-april-2026) |
| Maternity Leave | [Maternity Leave](https://www.gov.uk/maternity-pay-leave) |
| Paternity Leave | [Paternity Leave](https://www.gov.uk/paternity-pay-leave/leave) |
| Adoption Leave | [Adoption Leave](https://www.gov.uk/adoption-pay-leave) |
| Shared Parental Leave | [Shared Parental Leave](https://www.gov.uk/shared-parental-leave-and-pay) |
| Neonatal Care Leave | [Neonatal Care Leave](https://www.gov.uk/neonatal-care-pay-leave/what-you-get) |
| Parental Bereavement Leave | [Parental Bereavement Leave](https://www.gov.uk/parental-bereavement-pay-leave/what-you-are-entitled-to) |
| Parental Leave | [Parental Leave](https://www.gov.uk/parental-leave/entitlement) |
| Carer's Leave | [Carer's Leave](https://www.gov.uk/carers-leave) |
| Time Off for Dependants | [Time Off for Dependants](https://www.gov.uk/time-off-for-dependants) |
| Unpaid Leave | [Unpaid Leave](https://www.gov.uk/career-breaks) |

Additional checks: [maternity pay](https://www.gov.uk/maternity-pay-leave/pay),
[adoption pay](https://www.gov.uk/adoption-pay-leave/pay),
[shared parental blocks](https://www.gov.uk/shared-parental-leave-and-pay/booking-blocks-of-leave),
[annual leave carry-over and leave years](https://www.gov.uk/holiday-entitlement-rights/calculate-leave-entitlement).

## T8.2 regular-pattern computation (checked 2026-11-03)

- [Holiday entitlement](https://www.gov.uk/holiday-entitlement-rights): regular part-time patterns receive proportional entitlement; bank holidays may be included. The official three-day example is 16.8 days from the five-day 28-day allowance.
- [Calculating leave entitlement](https://www.gov.uk/holiday-entitlement-rights/calculate-leave-entitlement): starters receive a proportion of the leave year, with a pro-rata first month permitted. Regular-hours accrual can use twelfths. Irregular-hours and part-year accrual requires actual hours, which these fixed-pattern calculations do not infer.

Implementation policy: amounts are standard company days (company weekly working hours divided by company working days). A personal short day consumes the corresponding fraction, and entitlement uses personal weekly hours / company weekly hours, capped at full-time entitlement. Assignment history applies on its effective dates. Starter/leaver pro-rata uses inclusive employment calendar days over the actual leave year (365/366 days). Exact rational arithmetic avoids rounding drift; entitlements round upward once to 0.01 day. Monthly configuration posts completed leave months, with partial employment months pro-rated. This is a company accrual policy, not an irregular-hours statutory calculator. Missing bank-holiday year coverage is an explicit error. Year-wide scheduled bank holidays and paid closures reserve days once, only on personal working days, without overlap charges. Manual grants remain available for reviewed exceptional/irregular cases; no automatic regular-pattern grants for zero-hours/casual assignments.
