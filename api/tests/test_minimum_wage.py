"""The T6.6 basic-pay estimate uses the effective date, exact age and unrounded hourly rate."""

from datetime import date
from decimal import Decimal

import pytest

from app.modules.employees.compensation_schemas import CompensationIn
from app.modules.employees.minimum_wage import wage_check


@pytest.mark.parametrize(
    ("born", "effective", "minimum"),
    [
        (date(2005, 4, 2), date(2026, 4, 1), "10.85"),
        (date(2005, 4, 1), date(2026, 4, 1), "12.71"),
        (date(2008, 4, 2), date(2026, 4, 1), "8.00"),
        (date(1990, 1, 1), date(2026, 3, 31), "12.21"),
        (date(1990, 1, 1), date(2027, 4, 1), "13.21"),
    ],
)
def test_age_and_rate_boundaries(born: date, effective: date, minimum: str) -> None:
    result = wage_check(
        CompensationIn(amount=Decimal("10"), frequency="hourly", effective_from=effective), born
    )
    assert result.minimum_rate == Decimal(minimum)
    assert result.below_minimum == (Decimal("10") < Decimal(minimum))


@pytest.mark.parametrize(
    ("frequency", "amount"), [("annual", "26436.8"), ("monthly", "2203.07"), ("hourly", "12.71")]
)
def test_frequency_conversion(frequency: str, amount: str) -> None:
    body = CompensationIn.model_validate(
        {
            "amount": amount,
            "frequency": frequency,
            "effective_from": "2026-04-01",
            "contracted_hours_per_week": "40",
        }
    )
    result = wage_check(body, date(1990, 1, 1))
    assert result.below_minimum is False
    assert result.hourly_rate == Decimal("12.71")


def test_missing_data_and_unknown_rates_never_claim_a_pass() -> None:
    body = CompensationIn.model_validate(
        {"amount": "10000", "frequency": "annual", "effective_from": "2026-04-01"}
    )
    assert wage_check(body, date(1990, 1, 1)).below_minimum is None
    assert wage_check(body, None).minimum_rate is None
    body.effective_from = date(2099, 1, 1)
    assert wage_check(body, date(1990, 1, 1)).minimum_rate is None
