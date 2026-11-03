"""Sponsor reporting choices and official sources, checked on 2026-11-03."""

CHECKED_ON = "2026-11-03"
SPONSOR_GUIDANCE = "https://www.gov.uk/government/publications/workers-and-temporary-workers-guidance-for-sponsors-part-3-sponsor-duties-and-compliance/workers-and-temporary-workers-guidance-for-sponsors-part-3-sponsor-duties-and-compliance-accessible"
GLOSSARY = "https://www.gov.uk/government/publications/workers-and-temporary-workers-guidance-for-sponsors-glossary/workers-and-temporary-workers-guidance-for-sponsors-glossary-accessible#working-days"
BANK_HOLIDAYS = "https://www.gov.uk/bank-holidays"
CHANGE_TYPES = (
    ("did_not_start", "Didn't start work"),
    ("unauthorised_absence", "Unauthorised absence of more than 10 working days"),
    ("sponsorship_stopped", "Left, or sponsorship stopped"),
    ("salary_reduced", "Salary reduced"),
    ("job_or_soc_changed", "Change of job or SOC code"),
    ("work_location_changed", "Change of main work location"),
    ("working_hours_changed", "Change in working hours"),
    ("unpaid_reduced_absence", "Unpaid or reduced-pay absence over 4 weeks in a year"),
    ("other", "Other reportable change"),
)
ORG_CHANGE_TYPES = (
    ("address", "Address changed"),
    ("ownership", "Ownership changed"),
    ("name", "Organisation name changed"),
    ("key_personnel", "Other key personnel changed"),
    ("ao_or_key_contact", "Authorising Officer or Key Contact replacement"),
    ("other", "Other organisation change"),
)
