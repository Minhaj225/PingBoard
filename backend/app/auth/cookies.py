"""Refresh-token cookie handling, kept in one place so the flags can't drift."""

from __future__ import annotations

from fastapi import Response

from app.core.config import get_settings


def set_refresh_cookie(response: Response, raw_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=raw_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        # Unreadable from JavaScript, so an XSS bug cannot exfiltrate it.
        httponly=True,
        # SameSite=Lax already blocks cross-site POSTs from carrying the cookie,
        # which is what makes the refresh endpoint safe without a CSRF token.
        samesite=settings.COOKIE_SAMESITE,
        secure=settings.cookie_secure,
        path=settings.REFRESH_COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
    )


def clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    # Path and domain must match the original cookie or the browser keeps it.
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
        secure=settings.cookie_secure,
    )
