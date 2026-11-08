"""T16.2: a paid plan unlocks writes; free and lapsed plans are read-only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from app.modules.billing.entitlements import is_entitled, is_gated

NOW = datetime(2026, 11, 8, 12, tzinfo=UTC)


def _company(**values: Any) -> Any:
    base = {
        "plan": "free",
        "subscription_status": None,
        "subscription_ends_at": None,
        "payment_grace_ends_at": None,
    }
    return SimpleNamespace(**(base | values))


@pytest.mark.parametrize(
    ("company", "entitled"),
    [
        (_company(), False),
        (_company(plan="annual", subscription_status="active"), True),
        # Annual follows Stripe's status, not our copy of the period end (renewal moves it on).
        (
            _company(
                plan="annual",
                subscription_status="active",
                subscription_ends_at=NOW - timedelta(hours=1),
            ),
            True,
        ),
        (_company(plan="annual", subscription_status="past_due"), True),
        (
            _company(
                plan="annual",
                subscription_status="past_due",
                payment_grace_ends_at=NOW + timedelta(seconds=1),
            ),
            True,
        ),
        (
            _company(plan="annual", subscription_status="past_due", payment_grace_ends_at=NOW),
            False,
        ),
        (_company(plan="annual", subscription_status="unpaid"), False),
        (_company(plan="annual", subscription_status="canceled"), False),
        (
            _company(
                plan="ten_year",
                subscription_status="active",
                subscription_ends_at=NOW + timedelta(days=1),
            ),
            True,
        ),
        (_company(plan="ten_year", subscription_status="active", subscription_ends_at=NOW), False),
        (_company(plan="ten_year", subscription_status="refunded"), False),
    ],
)
def test_who_is_entitled(company: Any, entitled: bool) -> None:
    assert is_entitled(company, NOW) is entitled


@pytest.mark.parametrize(
    ("method", "permission", "gated"),
    [
        ("GET", "employee.profile.read", False),
        ("POST", "employee.profile.write", True),
        ("DELETE", "employee.profile.delete", True),
        ("POST", "employee.sensitive_data.read", False),  # reveal: a read sent as POST
        ("POST", "company.overview.read", False),  # marking notifications read
        ("POST", "billing.manage", False),
        ("PATCH", "company.profile.write", False),
        ("POST", "company.export", False),
        ("POST", "company.delete", False),
        ("POST", "soc.check.run", True),
    ],
)
def test_which_requests_need_a_plan(method: str, permission: str, gated: bool) -> None:
    assert is_gated(method, permission) is gated
