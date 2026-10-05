"""SSRF guard for user-supplied monitor URLs.

A monitor is, by design, a server-side fetch of a URL the user chose. Without a
guard that is a textbook SSRF primitive: the worker sits inside the private
network and would happily fetch the cloud metadata service, an internal admin
panel, or a database's HTTP port on the user's behalf.

The check is deliberately *resolve-then-inspect*: a hostname like
`metadata.evil.example` can resolve to 169.254.169.254, so validating the string
alone proves nothing. Every address the hostname resolves to must be public.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

ALLOWED_SCHEMES = frozenset({"http", "https"})
MAX_URL_LENGTH = 2048

# Ranges that are not "private" per ipaddress but must still be refused.
_EXTRA_BLOCKED = (
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / cloud metadata
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("100.64.0.0/10"),  # carrier-grade NAT
    ipaddress.ip_network("192.0.0.0/24"),  # IETF protocol assignments
    ipaddress.ip_network("192.0.2.0/24"),  # TEST-NET-1
    ipaddress.ip_network("198.18.0.0/15"),  # benchmarking
    ipaddress.ip_network("198.51.100.0/24"),  # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),  # TEST-NET-3
)


@dataclass(frozen=True)
class UrlCheck:
    ok: bool
    reason: str = ""

    def __bool__(self) -> bool:
        return self.ok


def is_blocked_address(address: str) -> bool:
    """True when an IP literal must never be fetched."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return True  # not an address at all — refuse rather than guess

    # An IPv4 address tunnelled through IPv6 (::ffff:127.0.0.1) has to be
    # judged on the address it actually reaches.
    if isinstance(ip, ipaddress.IPv6Address):
        mapped = ip.ipv4_mapped or (ipaddress.ip_address(ip.sixtofour) if ip.sixtofour else None)
        if mapped is not None:
            return is_blocked_address(str(mapped))

    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return True

    return any(ip in network for network in _EXTRA_BLOCKED)


def _resolve(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    return [str(info[4][0]) for info in infos]


def check_url(url: str, *, resolver: object = None) -> UrlCheck:
    """Validate a target URL, returning a reason when it is rejected.

    `resolver` is injectable so tests can exercise the DNS-rebinding path
    without real network lookups.
    """
    resolve = resolver if callable(resolver) else _resolve

    if not url or len(url) > MAX_URL_LENGTH:
        return UrlCheck(False, "URL is empty or too long")

    try:
        parts = urlsplit(url)
    except ValueError:
        return UrlCheck(False, "URL could not be parsed")

    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        return UrlCheck(False, "Only http:// and https:// URLs can be monitored")

    try:
        host = parts.hostname
    except ValueError:
        return UrlCheck(False, "URL host could not be parsed")

    if not host:
        return UrlCheck(False, "URL is missing a hostname")

    if parts.username or parts.password:
        # Credentials in the URL would be logged and leak into check results.
        return UrlCheck(False, "Credentials in the URL are not allowed")

    try:
        port = parts.port or (443 if parts.scheme.lower() == "https" else 80)
    except ValueError:
        return UrlCheck(False, "URL port is invalid")

    try:
        addresses = resolve(host, port)
    except OSError:
        return UrlCheck(False, f"Could not resolve host {host!r}")

    if not addresses:
        return UrlCheck(False, f"Could not resolve host {host!r}")

    # Every resolved address must be public: one private answer among several is
    # enough for an attacker, since which one gets used is not ours to control.
    for address in addresses:
        if is_blocked_address(address):
            return UrlCheck(False, f"{host} resolves to {address}, which is not a public address")

    return UrlCheck(True)


def is_safe_url(url: str) -> bool:
    return bool(check_url(url))
