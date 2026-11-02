"""Indicative salary check; rates verified 2026-11-02 against
https://www.gov.uk/national-minimum-wage-rates .

Compares basic pay to the age-band rate on the effective date. This does not infer apprentice
eligibility from the hire date: an apprenticeship can start later or have started elsewhere.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.modules.employees.compensation_schemas import CompensationIn, WageCheck

# Starts inclusive; year-end exclusive. Never reuse the last known rate indefinitely.
RATES = (
    (date(2024, 4, 1), date(2025, 4, 1), ("11.44", "8.60", "6.40")),
    (date(2025, 4, 1), date(2026, 4, 1), ("12.21", "10.00", "7.55")),
    (date(2026, 4, 1), date(2027, 4, 1), ("12.71", "10.85", "8.00")),
    (date(2027, 4, 1), date(2028, 4, 1), ("13.21", "11.27", "8.31")),
)


def wage_check(body: CompensationIn, born: date | None) -> WageCheck:
    hourly = body.amount if body.frequency == "hourly" else None
    if body.frequency != "hourly" and body.contracted_hours_per_week:
        annual = body.amount * (12 if body.frequency == "monthly" else 1)
        hourly = annual / (52 * body.contracted_hours_per_week)
    minimum = None
    message = "Add a date of birth to check the age-band minimum wage."
    if born is not None:
        day = body.effective_from
        age = day.year - born.year - ((day.month, day.day) < (born.month, born.day))
        rates = next((r for start, end, r in RATES if start <= day < end), None)
        if age < 16:
            message = "Check school-leaving-age eligibility before assessing minimum wage."
        elif rates is None:
            message = "No verified rate is available for this effective date. Check GOV.UK."
        else:
            minimum = Decimal(rates[0 if age >= 21 else 1 if age >= 18 else 2])
            message = (
                "Age-band estimate only; check apprentice eligibility, "
                "actual hours and deductions separately."
            )
    if hourly is None:
        message = "Add contracted hours a week to estimate the hourly rate. " + message
    below = hourly < minimum if hourly is not None and minimum is not None else None
    if below:
        message = "Basic hourly pay is below the age-band minimum wage. " + message
    return WageCheck(
        hourly_rate=hourly.quantize(Decimal("0.01")) if hourly is not None else None,
        minimum_rate=minimum,
        below_minimum=below,
        message=message,
    )
