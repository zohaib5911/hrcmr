"""The caller's address is read from forwarded headers only when a trusted proxy sent them."""

from __future__ import annotations

import ipaddress

import pytest

from app.core.client_ip import CLOUDFLARE_RANGES, RAILWAY_PRIVATE_RANGES, resolve_client_ip

RAILWAY = "100.64.0.7"
CLOUDFLARE_EDGE = "172.69.10.20"
VISITOR = "203.0.113.9"


def resolve(peer: str, **headers: str) -> str | None:
    return resolve_client_ip(
        peer,
        {name.replace("_", "-"): value for name, value in headers.items()},
        RAILWAY_PRIVATE_RANGES,
    )


def test_headers_from_a_stranger_are_ignored() -> None:
    assert resolve("198.51.100.4", x_real_ip=VISITOR, cf_connecting_ip=VISITOR) == "198.51.100.4"


def test_no_trusted_proxies_means_the_socket_address() -> None:
    assert resolve_client_ip("127.0.0.1", {"x-real-ip": VISITOR}, ()) == "127.0.0.1"


def test_through_cloudflare_and_railway_the_visitor_is_cf_connecting_ip() -> None:
    assert resolve(RAILWAY, x_real_ip=CLOUDFLARE_EDGE, cf_connecting_ip=VISITOR) == VISITOR


def test_a_forged_cloudflare_header_without_cloudflare_is_ignored() -> None:
    assert (
        resolve(RAILWAY, x_real_ip="198.51.100.77", cf_connecting_ip="1.2.3.4") == "198.51.100.77"
    )


def test_railway_alone_gives_x_real_ip() -> None:
    assert resolve(RAILWAY, x_real_ip=VISITOR) == VISITOR


def test_junk_in_a_header_falls_back_to_the_proxy_address() -> None:
    assert resolve(RAILWAY, x_real_ip="not-an-ip") == RAILWAY


def test_ipv6_is_matched_against_ipv6_ranges_only() -> None:
    assert (
        resolve("fd12::5", x_real_ip="2606:4700::1", cf_connecting_ip="2001:db8::9")
        == "2001:db8::9"
    )
    assert ipaddress.ip_address("fd12::5") in RAILWAY_PRIVATE_RANGES[1]


@pytest.mark.parametrize("peer", [None, "garbage"])
def test_an_unreadable_peer_is_returned_as_is(peer: str | None) -> None:
    assert resolve_client_ip(peer, {"x-real-ip": VISITOR}, RAILWAY_PRIVATE_RANGES) == peer


def test_the_fetched_cloudflare_list_replaces_the_built_in_one_and_can_be_dropped() -> None:
    from app.core.client_ip import cloudflare_ranges, use_cloudflare_ranges

    trusted = (ipaddress.ip_network("100.64.0.0/10"),)
    headers = {"x-real-ip": "203.0.113.9", "cf-connecting-ip": "198.51.100.7"}
    try:
        assert resolve_client_ip("100.64.0.2", headers, trusted) == "203.0.113.9"
        use_cloudflare_ranges(["203.0.113.0/24"])  # now "Cloudflare"
        assert resolve_client_ip("100.64.0.2", headers, trusted) == "198.51.100.7"
        use_cloudflare_ranges(["not a network"])  # unreadable: back to the built-in list
        assert cloudflare_ranges() == CLOUDFLARE_RANGES
    finally:
        use_cloudflare_ranges(None)
