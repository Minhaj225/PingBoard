"""Request and response bodies for the auth endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# Long passphrases are fine: `security._prehash` removes bcrypt's 72-byte cap.
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 256


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    name: str | None = Field(default=None, max_length=200)

    @field_validator("password")
    @classmethod
    def _reject_whitespace_only(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("password must not be entirely whitespace")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=PASSWORD_MAX_LENGTH)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str | None
    created_at: datetime


class TokenResponse(BaseModel):
    """The refresh token is not in this body — it is set as an httpOnly cookie."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105 — the OAuth scheme name, not a secret
    expires_in: int = Field(description="Access token lifetime in seconds.")
    user: UserRead
