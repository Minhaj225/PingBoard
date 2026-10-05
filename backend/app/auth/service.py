"""User registration and credential verification."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.security import hash_password, verify_password


class EmailAlreadyRegistered(Exception):
    """An account already exists for this email address."""


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(User.email == normalize_email(email)))


async def register_user(
    db: AsyncSession, *, email: str, password: str, name: str | None = None
) -> User:
    normalized = normalize_email(email)
    if await get_user_by_email(db, normalized) is not None:
        raise EmailAlreadyRegistered(normalized)

    user = User(email=normalized, name=name, password_hash=hash_password(password))
    db.add(user)
    await db.flush()
    return user


async def authenticate(db: AsyncSession, *, email: str, password: str) -> User | None:
    """Return the user when the credentials are valid, else `None`.

    The dummy verification on the miss path keeps the response time of "unknown
    email" close to that of "wrong password", so timing does not reveal which
    addresses are registered.
    """
    user = await get_user_by_email(db, email)

    if user is None or user.password_hash is None:
        _burn_timing(password)
        return None

    if not verify_password(password, user.password_hash):
        return None
    return user


# A pre-computed hash of a value no user can submit; verifying against it costs
# the same as a real bcrypt comparison.
_DUMMY_HASH = hash_password("pingboard-timing-equalizer")


def _burn_timing(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


async def upsert_github_user(
    db: AsyncSession, *, github_id: str, email: str, name: str | None
) -> User:
    """Find or create the account behind a GitHub identity.

    Matching on `github_id` first, then email, links an OAuth login to an
    existing password account instead of creating a duplicate.
    """
    normalized = normalize_email(email)

    user = await db.scalar(select(User).where(User.github_id == github_id))
    if user is None:
        user = await db.scalar(select(User).where(func.lower(User.email) == normalized))

    if user is None:
        user = User(email=normalized, name=name, github_id=github_id)
        db.add(user)
    else:
        user.github_id = github_id
        if not user.name and name:
            user.name = name

    await db.flush()
    return user
