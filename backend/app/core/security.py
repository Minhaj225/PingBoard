"""Password hashing and token primitives.

Two distinct kinds of token live here:

* **Access tokens** are short-lived signed JWTs. They are self-contained: the
  API validates one without touching the database.
* **Refresh tokens** are opaque high-entropy random strings. Only a SHA-256
  digest is persisted, and the raw value never leaves the client's cookie.
  SHA-256 (not bcrypt) is the right hash here precisely because the input is
  already 256+ bits of randomness — there is nothing to brute force, and the
  digest has to be cheap enough to look up on every refresh.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel, ConfigDict

from app.core.config import get_settings

ACCESS_TOKEN_TYPE = "access"  # noqa: S105 — a JWT claim value, not a secret
REFRESH_TOKEN_BYTES = 48


class InvalidToken(Exception):
    """Raised when a token is malformed, expired, or of the wrong type."""


class AccessTokenPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    sub: uuid.UUID
    typ: str
    jti: str
    iat: datetime
    exp: datetime


# --- Passwords -------------------------------------------------------------


def _prehash(password: str) -> bytes:
    """Normalise a password to a fixed-length input for bcrypt.

    bcrypt silently truncates anything past 72 bytes, which would quietly
    discard the tail of a long passphrase. Hashing to SHA-256 first and
    base64-encoding yields 44 ASCII bytes, so every password contributes its
    full entropy and no length limit has to be imposed on users.
    """
    return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(password), password_hash.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        # Malformed stored hash — treat as a failed verification, never a 500.
        return False


# --- Access tokens ---------------------------------------------------------


def create_access_token(user_id: uuid.UUID, *, expires_in: timedelta | None = None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    expiry = now + (expires_in or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    claims = {
        "sub": str(user_id),
        "typ": ACCESS_TOKEN_TYPE,
        "jti": secrets.token_urlsafe(16),
        "iat": int(now.timestamp()),
        "exp": int(expiry.timestamp()),
    }
    return jwt.encode(claims, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> AccessTokenPayload:
    """Decode and validate an access token, or raise `InvalidToken`."""
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "iat", "sub"]},
        )
    except InvalidTokenError as exc:
        raise InvalidToken(str(exc)) from exc

    if claims.get("typ") != ACCESS_TOKEN_TYPE:
        # A refresh or invite token must never be usable as a bearer token.
        raise InvalidToken("unexpected token type")

    try:
        return AccessTokenPayload.model_validate(claims)
    except ValueError as exc:
        raise InvalidToken("malformed token payload") from exc


# --- Opaque tokens (refresh, invites) --------------------------------------


def generate_opaque_token() -> tuple[str, str]:
    """Return `(raw, digest)`. Only the digest is ever persisted."""
    raw = secrets.token_urlsafe(REFRESH_TOKEN_BYTES)
    return raw, hash_opaque_token(raw)


def hash_opaque_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
