"""GitHub OAuth 2.0 authorization-code flow.

The `state` parameter is generated server-side, stored in Redis with a short
TTL and consumed exactly once on callback, which is what protects the flow
against login-CSRF.
"""

from __future__ import annotations

import secrets
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.redis import get_redis

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"  # noqa: S105 — an endpoint, not a secret
USER_URL = "https://api.github.com/user"
EMAILS_URL = "https://api.github.com/user/emails"

STATE_TTL_S = 600
_STATE_PREFIX = "oauth:github:state:"


class GitHubOAuthError(Exception):
    """The OAuth exchange failed or returned something unusable."""


async def create_state() -> str:
    state = secrets.token_urlsafe(32)
    await get_redis().set(f"{_STATE_PREFIX}{state}", "1", ex=STATE_TTL_S)
    return state


async def consume_state(state: str) -> bool:
    """Atomically validate and burn a state value, so it cannot be replayed."""
    deleted = await get_redis().delete(f"{_STATE_PREFIX}{state}")
    return bool(deleted)


def authorize_url(state: str) -> str:
    settings = get_settings()
    params = {
        "client_id": settings.GITHUB_CLIENT_ID or "",
        "redirect_uri": settings.GITHUB_REDIRECT_URI or "",
        "scope": "read:user user:email",
        "state": state,
        "allow_signup": "true",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(client: httpx.AsyncClient, code: str) -> str:
    settings = get_settings()
    response = await client.post(
        TOKEN_URL,
        data={
            "client_id": settings.GITHUB_CLIENT_ID,
            "client_secret": settings.GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": settings.GITHUB_REDIRECT_URI,
        },
        headers={"Accept": "application/json"},
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()

    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise GitHubOAuthError(str(payload.get("error_description") or "no access_token returned"))
    return token


async def fetch_identity(client: httpx.AsyncClient, token: str) -> tuple[str, str, str | None]:
    """Return `(github_id, email, name)` for the authenticated GitHub user."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    profile_response = await client.get(USER_URL, headers=headers)
    profile_response.raise_for_status()
    profile: dict[str, Any] = profile_response.json()

    github_id = profile.get("id")
    if github_id is None:
        raise GitHubOAuthError("GitHub profile had no id")

    email = profile.get("email")
    if not email:
        # A user with a private email address needs the dedicated endpoint.
        email = await _primary_verified_email(client, headers)

    if not email:
        raise GitHubOAuthError("no verified email address available on this GitHub account")

    return str(github_id), email, profile.get("name")


async def _primary_verified_email(client: httpx.AsyncClient, headers: dict[str, str]) -> str | None:
    response = await client.get(EMAILS_URL, headers=headers)
    response.raise_for_status()
    emails: list[dict[str, Any]] = response.json()

    for entry in emails:
        if entry.get("primary") and entry.get("verified"):
            return str(entry["email"])
    for entry in emails:
        if entry.get("verified"):
            return str(entry["email"])
    return None
