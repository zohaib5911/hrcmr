"""The caller's address, believed only when it comes through a proxy we trust.

Headers such as ``X-Real-IP`` and ``CF-Connecting-IP`` are plain text any client can send, so they
count only when the connection itself arrives from a proxy of ours. The chain in production is
browser, then Cloudflare, then Railway's edge, then this API:

* The address that connects to the API is Railway's edge, on its private network
  (``RAILWAY_PRIVATE_RANGES``, or the ``TRUSTED_PROXY_CIDRS`` setting). Anything else, including
  every request on a developer machine, is taken at its socket address and its headers ignored.
* From that edge, ``X-Real-IP`` is the address that connected to Railway. If that address is one of
  Cloudflare's published ranges, the request really came through Cloudflare and
  ``CF-Connecting-IP`` is the visitor. If not, ``X-Real-IP`` itself is the best answer, and a
  forged ``CF-Connecting-IP`` from someone who bypassed Cloudflare is ignored.
"""

from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request

    from app.core.config import Settings

type Network = ipaddress.IPv4Network | ipaddress.IPv6Network

# Cloudflare's published ranges, https://www.cloudflare.com/ips-v4 and /ips-v6, checked 2026-11-02.
# Refresh them from there if Cloudflare announces a change.
CLOUDFLARE_RANGES: tuple[Network, ...] = tuple(
    ipaddress.ip_network(cidr)
    for cidr in (
        "173.245.48.0/20",
        "103.21.244.0/22",
        "103.22.200.0/22",
        "103.31.4.0/22",
        "141.101.64.0/18",
        "108.162.192.0/18",
        "190.93.240.0/20",
        "188.114.96.0/20",
        "197.234.240.0/22",
        "198.41.128.0/17",
        "162.158.0.0/15",
        "104.16.0.0/13",
        "104.24.0.0/14",
        "172.64.0.0/13",
        "131.0.72.0/22",
        "2400:cb00::/32",
        "2606:4700::/32",
        "2803:f800::/32",
        "2405:b500::/32",
        "2405:8100::/32",
        "2a06:98c0::/29",
        "2c0f:f248::/32",
    )
)

# Railway reaches a service from its private network: the carrier-grade NAT block for IPv4 and the
# unique-local block for IPv6.
RAILWAY_PRIVATE_RANGES: tuple[Network, ...] = (
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("fd00::/8"),
)


def trusted_proxy_networks(settings: Settings) -> tuple[Network, ...]:
    """Who may vouch for a visitor's address: the configured list, else Railway when deployed."""
    if settings.trusted_proxy_cidrs:
        return tuple(
            ipaddress.ip_network(part.strip(), strict=False)
            for part in settings.trusted_proxy_cidrs.split(",")
            if part.strip()
        )
    return RAILWAY_PRIVATE_RANGES if settings.app_env.is_deployed else ()


def _parse(value: str | None) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address((value or "").strip())
    except ValueError:
        return None


def _within(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address, networks: tuple[Network, ...]
) -> bool:
    return any(address.version == network.version and address in network for network in networks)


def resolve_client_ip(
    peer: str | None,
    headers: dict[str, str],
    trusted: tuple[Network, ...],
) -> str | None:
    """The visitor's address. ``headers`` must have lower-case names."""
    peer_address = _parse(peer)
    if peer_address is None or not _within(peer_address, trusted):
        return peer
    real = _parse(headers.get("x-real-ip"))
    if real is None:
        return peer
    if _within(real, CLOUDFLARE_RANGES):
        visitor = _parse(headers.get("cf-connecting-ip"))
        if visitor is not None:
            return str(visitor)
    return str(real)


def client_ip_of(request: Request) -> str | None:
    settings: Settings = request.app.state.settings
    peer = request.client.host if request.client else None
    headers = {name: request.headers.get(name, "") for name in ("x-real-ip", "cf-connecting-ip")}
    return resolve_client_ip(peer, headers, trusted_proxy_networks(settings))
