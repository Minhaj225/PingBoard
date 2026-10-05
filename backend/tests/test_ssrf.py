from __future__ import annotations

import pytest

from app.monitors.ssrf import check_url, is_blocked_address, is_safe_url


def fake_resolver(mapping: dict[str, list[str]]):
    def resolve(host: str, port: int) -> list[str]:
        if host not in mapping:
            raise OSError(f"cannot resolve {host}")
        return mapping[host]

    return resolve


PUBLIC = fake_resolver({"example.com": ["93.184.216.34"]})


class TestBlockedAddresses:
    @pytest.mark.parametrize(
        "address",
        [
            "127.0.0.1",  # loopback
            "127.5.5.5",  # the whole 127/8 range, not just .0.1
            "0.0.0.0",  # unspecified -> "this host"
            "169.254.169.254",  # AWS/GCP/Azure metadata
            "169.254.1.1",  # link-local generally
            "10.0.0.5",  # RFC1918
            "172.16.0.1",
            "172.31.255.254",
            "192.168.1.1",
            "100.64.0.1",  # carrier-grade NAT
            "224.0.0.1",  # multicast
            "255.255.255.255",  # broadcast / reserved
            "::1",  # IPv6 loopback
            "fe80::1",  # IPv6 link-local
            "fc00::1",  # IPv6 unique-local
            "::ffff:127.0.0.1",  # IPv4-mapped loopback
            "::ffff:169.254.169.254",
            "::",  # unspecified
            "198.18.0.1",  # benchmarking
            "192.0.2.1",  # TEST-NET-1
        ],
    )
    def test_blocked(self, address: str) -> None:
        assert is_blocked_address(address)

    @pytest.mark.parametrize(
        "address",
        ["93.184.216.34", "1.1.1.1", "8.8.8.8", "2606:4700:4700::1111"],
    )
    def test_allowed(self, address: str) -> None:
        assert not is_blocked_address(address)

    def test_non_address_is_blocked(self) -> None:
        assert is_blocked_address("not-an-ip")


class TestSchemes:
    @pytest.mark.parametrize(
        "url",
        [
            "ftp://example.com/x",
            "file:///etc/passwd",
            "gopher://example.com",
            "redis://example.com:6379",
            "dict://example.com",
            "jar:http://example.com!/",
            "//example.com/no-scheme",
            "javascript:alert(1)",
            "data:text/plain,hello",
        ],
    )
    def test_non_http_schemes_rejected(self, url: str) -> None:
        assert not check_url(url, resolver=PUBLIC)

    @pytest.mark.parametrize("url", ["http://example.com", "https://example.com/health"])
    def test_http_schemes_allowed(self, url: str) -> None:
        assert check_url(url, resolver=PUBLIC)

    def test_scheme_case_is_ignored(self) -> None:
        assert check_url("HTTPS://example.com", resolver=PUBLIC)


class TestInternalTargets:
    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost",
            "http://localhost:8000/health",
            "http://127.0.0.1",
            "http://169.254.169.254/latest/meta-data/",
            "http://[::1]:8000",
            "http://10.0.0.1/admin",
            "http://192.168.0.1",
            "http://0.0.0.0:8000",
        ],
    )
    def test_internal_targets_rejected(self, url: str) -> None:
        """These must fail on the literal address, before any DNS lookup."""
        resolver = fake_resolver({"localhost": ["127.0.0.1"]})
        result = check_url(url, resolver=resolver)
        assert not result
        assert result.reason


class TestDnsRebinding:
    def test_hostname_resolving_to_metadata_is_rejected(self) -> None:
        """The whole reason the guard resolves rather than pattern-matches."""
        resolver = fake_resolver({"metadata.evil.example": ["169.254.169.254"]})
        result = check_url("http://metadata.evil.example/", resolver=resolver)
        assert not result
        assert "169.254.169.254" in result.reason

    def test_one_private_answer_among_public_ones_is_rejected(self) -> None:
        resolver = fake_resolver({"mixed.example": ["93.184.216.34", "127.0.0.1"]})
        assert not check_url("http://mixed.example/", resolver=resolver)

    def test_unresolvable_host_is_rejected(self) -> None:
        result = check_url("http://nx.invalid/", resolver=fake_resolver({}))
        assert not result
        assert "resolve" in result.reason.lower()

    def test_empty_resolution_is_rejected(self) -> None:
        assert not check_url("http://void.example/", resolver=fake_resolver({"void.example": []}))


class TestMalformedInput:
    @pytest.mark.parametrize("url", ["", "   ", "http://", "https://", "not a url"])
    def test_rejected(self, url: str) -> None:
        assert not check_url(url, resolver=PUBLIC)

    def test_credentials_in_url_rejected(self) -> None:
        result = check_url("http://user:pass@example.com/", resolver=PUBLIC)
        assert not result
        assert "credential" in result.reason.lower()

    def test_overlong_url_rejected(self) -> None:
        assert not check_url("http://example.com/" + "a" * 3000, resolver=PUBLIC)

    def test_invalid_port_rejected(self) -> None:
        assert not check_url("http://example.com:99999/", resolver=PUBLIC)


def test_is_safe_url_wrapper_returns_bool() -> None:
    """Rejected on scheme alone, so the suite never depends on real DNS."""
    assert is_safe_url("ftp://example.com") is False
