"""Authentication endpoints."""

from __future__ import annotations

import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse

from app.auth import github, service, tokens
from app.auth.cookies import clear_refresh_cookie, set_refresh_cookie
from app.auth.deps import CurrentUser, DbSession
from app.auth.models import User
from app.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserRead
from app.core.config import Settings, get_settings
from app.core.ratelimit import auth_rate_limit
from app.core.security import create_access_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

SettingsDep = Annotated[Settings, Depends(get_settings)]
RefreshCookie = Annotated[str | None, Cookie(alias="pb_refresh")]

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Incorrect email or password",
    headers={"WWW-Authenticate": "Bearer"},
)


def _token_response(settings: Settings, user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserRead.model_validate(user),
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth_rate_limit)],
    summary="Create an account and start a session",
)
async def register(
    payload: RegisterRequest,
    response: Response,
    db: DbSession,
    settings: SettingsDep,
) -> TokenResponse:
    try:
        user = await service.register_user(
            db, email=payload.email, password=payload.password, name=payload.name
        )
    except service.EmailAlreadyRegistered as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from exc

    raw_refresh = await tokens.issue_refresh_token(db, user.id)
    await db.commit()

    set_refresh_cookie(response, raw_refresh)
    return _token_response(settings, user)


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(auth_rate_limit)],
    summary="Exchange credentials for an access token",
)
async def login(
    payload: LoginRequest,
    response: Response,
    db: DbSession,
    settings: SettingsDep,
) -> TokenResponse:
    user = await service.authenticate(db, email=payload.email, password=payload.password)
    if user is None:
        raise _INVALID_CREDENTIALS

    raw_refresh = await tokens.issue_refresh_token(db, user.id)
    await db.commit()

    set_refresh_cookie(response, raw_refresh)
    return _token_response(settings, user)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate the refresh cookie and mint a new access token",
)
async def refresh(
    response: Response,
    db: DbSession,
    settings: SettingsDep,
    pb_refresh: RefreshCookie = None,
) -> TokenResponse:
    if not pb_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token"
        )

    try:
        user_id, new_raw = await tokens.rotate_refresh_token(db, pb_refresh)
    except tokens.RefreshTokenError as exc:
        # Commit so that a reuse-triggered mass revocation is not rolled back.
        await db.commit()
        clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        ) from exc

    user = await db.get(User, user_id)
    if user is None:
        await db.commit()
        clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")

    await db.commit()
    set_refresh_cookie(response, new_raw)
    return _token_response(settings, user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the current refresh token",
)
async def logout(
    response: Response,
    db: DbSession,
    pb_refresh: RefreshCookie = None,
) -> None:
    # Idempotent: logging out without a cookie still succeeds.
    if pb_refresh:
        await tokens.revoke_refresh_token(db, pb_refresh)
        await db.commit()
    clear_refresh_cookie(response)


@router.get("/me", response_model=UserRead, summary="The authenticated user")
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


# --- GitHub OAuth ----------------------------------------------------------


@router.get(
    "/github/login",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    summary="Begin the GitHub authorization-code flow",
)
async def github_login(settings: SettingsDep) -> RedirectResponse:
    if not settings.github_oauth_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub sign-in is not configured on this deployment",
        )
    state = await github.create_state()
    return RedirectResponse(github.authorize_url(state))


@router.get(
    "/github/callback",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    summary="Complete the GitHub flow and start a session",
)
async def github_callback(
    db: DbSession,
    settings: SettingsDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Set the refresh cookie and bounce back to the SPA.

    No token is placed in the redirect URL: the browser lands on the frontend
    with only the httpOnly cookie, and the SPA calls `/auth/refresh` to obtain
    its first access token. That keeps credentials out of history and referrers.
    """
    if error:
        return _oauth_failure(settings, error)
    if not settings.github_oauth_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub sign-in is not configured on this deployment",
        )
    if not code or not state or not await github.consume_state(state):
        return _oauth_failure(settings, "invalid_state")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            access_token = await github.exchange_code(client, code)
            github_id, email, name = await github.fetch_identity(client, access_token)
    except (httpx.HTTPError, github.GitHubOAuthError):
        logger.warning("github oauth exchange failed", exc_info=True)
        return _oauth_failure(settings, "exchange_failed")

    user = await service.upsert_github_user(db, github_id=github_id, email=email, name=name)
    raw_refresh = await tokens.issue_refresh_token(db, user.id)
    await db.commit()

    redirect = RedirectResponse(f"{settings.FRONTEND_URL}/auth/callback")
    set_refresh_cookie(redirect, raw_refresh)
    return redirect


def _oauth_failure(settings: Settings, reason: str) -> RedirectResponse:
    return RedirectResponse(f"{settings.FRONTEND_URL}/login?oauth_error={reason}")
