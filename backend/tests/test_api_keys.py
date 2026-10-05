from __future__ import annotations

from app.core.security import hash_opaque_token
from app.orgs.api_keys import KEY_PREFIX, generate_key


class TestKeyGeneration:
    def test_raw_key_carries_a_recognisable_prefix(self) -> None:
        """A prefix makes a leaked key greppable and scanner-detectable."""
        raw, _ = generate_key()
        assert raw.startswith(KEY_PREFIX)

    def test_digest_matches_the_raw_key(self) -> None:
        raw, digest = generate_key()
        assert hash_opaque_token(raw) == digest

    def test_the_raw_key_is_not_the_digest(self) -> None:
        """The whole point: what's stored must not be usable as a credential."""
        raw, digest = generate_key()
        assert raw != digest
        assert raw not in digest

    def test_digest_is_sha256_hex(self) -> None:
        _, digest = generate_key()
        assert len(digest) == 64
        assert set(digest) <= set("0123456789abcdef")

    def test_keys_are_unique(self) -> None:
        assert len({generate_key()[0] for _ in range(500)}) == 500

    def test_entropy_is_substantial(self) -> None:
        raw, _ = generate_key()
        # 32 random bytes, urlsafe-base64 encoded, plus the prefix.
        assert len(raw) - len(KEY_PREFIX) >= 40

    def test_digest_is_deterministic(self) -> None:
        """Lookup is by digest, so the same key must always hash the same."""
        raw, digest = generate_key()
        assert hash_opaque_token(raw) == digest
        assert hash_opaque_token(raw) == digest
