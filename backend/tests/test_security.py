from __future__ import annotations

import uuid
from datetime import timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import (
    InvalidToken,
    create_access_token,
    decode_access_token,
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_round_trip(self) -> None:
        digest = hash_password("correct-horse-battery-staple")
        assert verify_password("correct-horse-battery-staple", digest)

    def test_wrong_password_rejected(self) -> None:
        assert not verify_password("nope", hash_password("secret-passphrase"))

    def test_salted(self) -> None:
        assert hash_password("same-input") != hash_password("same-input")

    def test_malformed_stored_hash_is_false_not_an_error(self) -> None:
        assert not verify_password("anything", "not-a-bcrypt-hash")

    @pytest.mark.parametrize("length", [71, 72, 73, 200])
    def test_long_passwords_keep_full_entropy(self, length: int) -> None:
        """bcrypt truncates at 72 bytes; the SHA-256 pre-hash must prevent that.

        Two passwords sharing a 72-byte prefix have to stay distinguishable.
        """
        base = "a" * length
        digest = hash_password(base)
        assert verify_password(base, digest)
        assert not verify_password(base + "different-tail", digest)

    def test_non_ascii_password(self) -> None:
        secret = "пароль-🔒-переходный"
        assert verify_password(secret, hash_password(secret))


class TestAccessTokens:
    def test_round_trip_carries_subject(self) -> None:
        user_id = uuid.uuid4()
        payload = decode_access_token(create_access_token(user_id))
        assert payload.sub == user_id
        assert payload.typ == "access"

    def test_each_token_is_unique(self) -> None:
        user_id = uuid.uuid4()
        first = decode_access_token(create_access_token(user_id))
        second = decode_access_token(create_access_token(user_id))
        assert first.jti != second.jti

    def test_tampered_signature_rejected(self) -> None:
        token = create_access_token(uuid.uuid4())
        with pytest.raises(InvalidToken):
            decode_access_token(token[:-1] + ("A" if token[-1] != "A" else "B"))

    def test_expired_token_rejected(self) -> None:
        token = create_access_token(uuid.uuid4(), expires_in=timedelta(seconds=-1))
        with pytest.raises(InvalidToken):
            decode_access_token(token)

    def test_token_signed_with_another_secret_rejected(self) -> None:
        settings = get_settings()
        forged = jwt.encode(
            {"sub": str(uuid.uuid4()), "typ": "access", "iat": 0, "exp": 9999999999, "jti": "x"},
            "an-attacker-controlled-secret-long-enough-for-hs256",
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(InvalidToken):
            decode_access_token(forged)

    def test_alg_none_rejected(self) -> None:
        """The classic JWT downgrade: an unsigned token must never validate."""
        forged = jwt.encode(
            {"sub": str(uuid.uuid4()), "typ": "access", "iat": 0, "exp": 9999999999, "jti": "x"},
            key="",
            algorithm="none",
        )
        with pytest.raises(InvalidToken):
            decode_access_token(forged)

    def test_non_access_token_type_rejected(self) -> None:
        settings = get_settings()
        other = jwt.encode(
            {"sub": str(uuid.uuid4()), "typ": "refresh", "iat": 0, "exp": 9999999999, "jti": "x"},
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(InvalidToken):
            decode_access_token(other)

    def test_garbage_rejected(self) -> None:
        with pytest.raises(InvalidToken):
            decode_access_token("not.a.jwt")


class TestOpaqueTokens:
    def test_digest_matches_and_raw_is_not_the_digest(self) -> None:
        raw, digest = generate_opaque_token()
        assert hash_opaque_token(raw) == digest
        assert raw != digest

    def test_digest_is_sha256_hex(self) -> None:
        _, digest = generate_opaque_token()
        assert len(digest) == 64
        assert set(digest) <= set("0123456789abcdef")

    def test_tokens_are_unique(self) -> None:
        assert len({generate_opaque_token()[0] for _ in range(200)}) == 200
