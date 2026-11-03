"""Original summaries checked against GOV.UK on 2026-11-03; see data/leave/SOURCES.md."""

from __future__ import annotations

from datetime import date
from typing import Any

CHECKED_ON = date(2026, 11, 3)
DEFAULT_TYPES: tuple[dict[str, Any], ...] = (
    {
        "seed_key": "annual",
        "name": "Annual Leave",
        "is_paid": True,
        "counts_toward_statutory": True,
        "days_per_year": "28.00",
        "carry_over_limit_days": "5.00",
        "colour": "blue",
        "rule_text": "5.6 weeks of paid holiday; 28 days includes bank holidays for a five-day "
        "week. Pro-rate for the working pattern and time employed. Five days is the "
        "company carry-over default; statutory family-leave, sickness and other "
        "protected carry-over can require more.",
        "source_url": "https://www.gov.uk/holiday-entitlement-rights",
    },
    {
        "seed_key": "sick",
        "name": "Sick Leave",
        "is_paid": True,
        "colour": "orange",
        "rule_text": "Eligible employees receive Statutory Sick Pay from the first full day of "
        "sickness absence from 6 April 2026, for up to 28 weeks. Company sick pay may "
        "provide more.",
        "source_url": "https://www.gov.uk/guidance/sickness-absences-that-start-before-and-end-on-or-after-6-april-2026",
    },
    {
        "seed_key": "maternity",
        "name": "Maternity Leave",
        "is_paid": True,
        "colour": "green",
        "rule_text": "Up to 52 weeks of statutory maternity leave. Statutory Maternity Pay lasts "
        "up to 39 weeks where eligible; leave and pay have separate conditions.",
        "source_url": "https://www.gov.uk/maternity-pay-leave",
    },
    {
        "seed_key": "paternity",
        "name": "Paternity Leave",
        "is_paid": True,
        "colour": "green",
        "rule_text": "Up to two weeks, together or as separate one-week blocks, ending within 52 "
        "weeks of birth (or the due date for an early birth). Adoption and Northern "
        "Ireland rules differ. Statutory pay depends on eligibility.",
        "source_url": "https://www.gov.uk/paternity-pay-leave/leave",
    },
    {
        "seed_key": "adoption",
        "name": "Adoption Leave",
        "is_paid": True,
        "colour": "green",
        "rule_text": "Up to 52 weeks of statutory adoption leave for one adopter in a couple. "
        "Statutory Adoption Pay is available subject to eligibility, for up to 39 "
        "weeks.",
        "source_url": "https://www.gov.uk/adoption-pay-leave",
    },
    {
        "seed_key": "shared_parental",
        "name": "Shared Parental Leave",
        "is_paid": True,
        "colour": "green",
        "rule_text": "Eligible parents can share up to 50 weeks of leave and 37 weeks of pay in "
        "the first year after birth or placement. Each parent may book three blocks; "
        "more can be agreed with the employer.",
        "source_url": "https://www.gov.uk/shared-parental-leave-and-pay",
    },
    {
        "seed_key": "neonatal",
        "name": "Neonatal Care Leave",
        "is_paid": True,
        "colour": "green",
        "rule_text": "Eligible employees can take up to 12 weeks of neonatal care leave, within 68 "
        "weeks of birth. One week accrues for each seven continuous full days of "
        "neonatal care. Pay has separate eligibility conditions.",
        "source_url": "https://www.gov.uk/neonatal-care-pay-leave/what-you-get",
    },
    {
        "seed_key": "parental_bereavement",
        "name": "Parental Bereavement Leave",
        "is_paid": True,
        "colour": "red",
        "rule_text": "Eligible employees can take up to two weeks after a child's death or "
        "stillbirth, finishing within 56 weeks. Statutory Parental Bereavement Pay "
        "depends on separate eligibility conditions.",
        "source_url": "https://www.gov.uk/parental-bereavement-pay-leave/what-you-are-entitled-to",
    },
    {
        "seed_key": "parental",
        "name": "Parental Leave",
        "is_paid": False,
        "colour": "gray",
        "rule_text": "Eligible parents can take 18 weeks of unpaid leave per child up to their "
        "18th birthday. Normally no more than four weeks per child each year, in "
        "whole weeks, unless exceptions or an agreement apply.",
        "source_url": "https://www.gov.uk/parental-leave/entitlement",
    },
    {
        "seed_key": "carer",
        "name": "Carer's Leave",
        "is_paid": False,
        "colour": "gray",
        "rule_text": "Up to one normal working week of unpaid carer's leave in each 12 months to "
        "provide or arrange care for a dependant with a long-term care need. "
        "Available from the first day of employment.",
        "source_url": "https://www.gov.uk/carers-leave",
    },
    {
        "seed_key": "dependants",
        "name": "Time Off for Dependants",
        "is_paid": False,
        "colour": "gray",
        "rule_text": "Reasonable time off for an unexpected emergency involving a dependant. There "
        "is no fixed allowance and no requirement to pay; the employment contract may "
        "provide pay.",
        "source_url": "https://www.gov.uk/time-off-for-dependants",
    },
    {
        "seed_key": "unpaid",
        "name": "Unpaid Leave",
        "is_paid": False,
        "colour": "gray",
        "rule_text": "Company policy: unpaid time off by agreement. No automatic annual allowance "
        "is configured. Agree the terms with the employer; statutory leave rights are "
        "separate.",
        "source_url": "https://www.gov.uk/career-breaks",
    },
)
