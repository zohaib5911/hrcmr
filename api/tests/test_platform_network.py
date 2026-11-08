"""T17.1: the admin network allowlist (ADMIN_IP_ALLOWLIST). Unset means no restriction. When it is
set, an address must be one of its IPs or inside one of its networks, and an entry that does not
parse matches nothing, so a typo narrows access rather than widening it."""

from __future__ import annotations

import pytest

from app.modules.rbac.platform import ip_allowed


@pytest.mark.parametrize("ip", [None, "203.0.113.7", "not-an-ip"])
def test_an_unset_allowlist_restricts_nothing(ip: str | None) -> None:
    assert ip_allowed(ip, []) is True


def test_an_exact_address_matches() -> None:
    assert ip_allowed("203.0.113.7", ["203.0.113.7"]) is True
    assert ip_allowed("203.0.113.8", ["203.0.113.7"]) is False


def test_a_network_matches_its_addresses_only() -> None:
    assert ip_allowed("10.1.2.3", ["10.0.0.0/8"]) is True
    assert ip_allowed("11.0.0.1", ["10.0.0.0/8"]) is False


def test_an_ipv6_network_matches() -> None:
    assert ip_allowed("2001:db8::1", ["2001:db8::/32"]) is True
    assert ip_allowed("2001:dead::1", ["2001:db8::/32"]) is False


def test_a_missing_address_is_refused_when_an_allowlist_is_set() -> None:
    assert ip_allowed(None, ["10.0.0.0/8"]) is False


def test_an_unparseable_address_is_refused() -> None:
    assert ip_allowed("not-an-ip", ["10.0.0.0/8"]) is False


def test_an_unparseable_entry_matches_nothing_but_does_not_hide_the_others() -> None:
    assert ip_allowed("203.0.113.7", ["nonsense", "203.0.113.7"]) is True
    assert ip_allowed("203.0.113.8", ["nonsense"]) is False
