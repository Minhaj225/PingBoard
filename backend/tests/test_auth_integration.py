from __future__ import annotations

import uuid
from datetime import timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient

from app.auth.models import RefreshToken
from app.core.security import create_access_token, decode_access_token


class TestAuthRegister:
    """Tests for POST /auth/register."""

    async def test_register_creates_user_and_returns_tokens(
        self, client: AsyncClient, test_user_email: str, test_user_password: str
    ) -> None:
        response = await client.post(
            "/auth/register",
            json={"email": test_user_email, "password": test_user_password, "name": "Test User"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "expires_in" in data
        assert data["expires_in"] == 900  # 15 minutes
        assert "user" in data
        assert data["user"]["email"] == test_user_email
        assert data["user"]["name"] == "Test User"
        # Refresh token should be in cookie
        assert "pb_refresh" in response.cookies

    async def test_register_rejects_duplicate_email(
        self, client: AsyncClient, test_user_email: str, test_user_password: str
    ) -> None:
        # First registration
        await client.post(
            "/auth/register",
            json={"email": test_user_email, "password": test_user_password, "name": "Test User"},
        )
        # Second registration with same email
        response = await client.post(
            "/auth/register",
            json={"email": test_user_email, "password": test_user_password, "name": "Another User"},
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    async def test_register_rejects_invalid_email(
        self, client: AsyncClient, test_user_password: str
    ) -> None:
        response = await client.post(
            "/auth/register",
            json={"email": "not-an-email", "password": test_user_password, "name": "Test"},
        )
        assert response.status_code == 422

    async def test_register_rejects_short_password(
        self, client: AsyncClient, test_user_email: str
    ) -> None:
        response = await client.post(
            "/auth/register",
            json={"email": test_user_email, "password": "short", "name": "Test"},
        )
        assert response.status_code == 422


class TestAuthLogin:
    """Tests for POST /auth/login."""

    async def test_login_returns_tokens_for_valid_credentials(
        self, client: AsyncClient, test_user_email: str, test_user_password: str
    ) -> None:
        # First register
        await client.post(
            "/auth/register",
            json={"email": test_user_email, "password": test_user_password, "name": "Test User"},
        )
        # Then login
        response = await client.post(
            "/auth/login",
            json={"email": test_user_email, "password": test_user_password},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == test_user_email
        assert "pb_refresh" in response.cookies

    async def test_login_rejects_wrong_password(
        self, client: AsyncClient, test_user_email: str, test_user_password: str
    ) -> None:
        await client.post(
            "/auth/register",
            json={"email": test_user_email, "password": test_user_password, "name": "Test User"},
        )
        response = await client.post(
            "/auth/login",
            json={"email": test_user_email, "password": "WrongPassword123!"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect email or password"

    async def test_login_rejects_nonexistent_user(self, client: AsyncClient) -> None:
        response = await client.post(
            "/auth/login",
            json={"email": "nonexistent@example.com", "password": "AnyPassword123!"},
        )
        assert response.status_code == 401


class TestAuthRefresh:
    """Tests for POST /auth/refresh."""

    async def test_refresh_rotates_token_and_issues_new_access(
        self, client: AsyncClient, test_user_email: str, test_user_password: str
    ) -> None:
        # Register and get refresh cookie
        await client.post(
            "/auth/register",
            json={"email": test_user_email, "password": test_user_password, "name": "Test User"},
        )
        refresh_cookie = client.cookies.get("pb_refresh")
        assert refresh_cookie

        # Call refresh
        response = await client.post("/auth/refresh")
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        # New refresh cookie should be set
        new_refresh_cookie = response.cookies.get("pb_refresh")
        assert new_refresh_cookie
        assert new_refresh_cookie != refresh_cookie

    async def test_refresh_rejects_missing_cookie(self, client: AsyncClient) -> None:
        response = await client.post("/auth/refresh")
        assert response.status_code == 401
        assert response.json()["detail"] == "Missing refresh token"

    async def test_refresh_rejects_invalid_token(self, client: AsyncClient) -> None:
        client.cookies.set("pb_refresh", "invalid-token")
        response = await client.post("/auth/refresh")
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid refresh token"

    async def test_refresh_reuse_triggers_mass_revocation(
        self, client: AsyncClient, test_user_email: str, test_user_password: str
    ) -> None:
        """Test that reusing a refresh token revokes all sessions."""
        # Register
        await client.post(
            "/auth/register",
            json={"email": test_user_email, "password": test_user_password, "name": "Test User"},
        )
        refresh_cookie = client.cookies.get("pb_refresh")
        assert refresh_cookie

        # First refresh - should work
        response1 = await client.post("/auth/refresh")
        assert response1.status_code == 200
        new_cookie = response1.cookies.get("pb_refresh")
        assert new_cookie

        # Try to reuse the OLD refresh token - should fail with 401
        client.cookies.set("pb_refresh", refresh_cookie)
        response2 = await client.post("/auth/refresh")
        assert response2.status_code == 401

        # Even the new valid token should now be revoked
        client.cookies.set("pb_refresh", new_cookie)
        response3 = await client.post("/auth/refresh")
        assert response3.status_code == 401


class TestAuthLogout:
    """Tests for POST /auth/logout."""

    async def test_logout_revokes_refresh_token(
        self, client: AsyncClient, test_user_email: str, test_user_password: str
    ) -> None:
        await client.post(
            "/auth/register",
            json={"email": test_user_email, "password": test_user_password, "name": "Test User"},
        )
        response = await client.post("/auth/logout")
        assert response.status_code == 204
        # Cookie should be cleared
        assert "pb_refresh" in response.cookies
        assert response.cookies["pb_refresh"] == ""

        # Refresh should now fail
        response = await client.post("/auth/refresh")
        assert response.status_code == 401

    async def test_logout_idempotent(self, client: AsyncClient) -> None:
        """Logging out without a session should still succeed."""
        response = await client.post("/auth/logout")
        assert response.status_code == 204


class TestAuthMe:
    """Tests for GET /auth/me."""

    async def test_me_returns_current_user(
        self, client: AsyncClient, test_user_email: str, test_user_password: str
    ) -> None:
        await client.post(
            "/auth/register",
            json={"email": test_user_email, "password": test_user_password, "name": "Test User"},
        )
        # Get access token from register response
        register_response = await client.post(
            "/auth/login",
            json={"email": test_user_email, "password": test_user_password},
        )
        access_token = register_response.json()["access_token"]

        # Call /me with bearer token
        response = await client.get(
            "/auth/me", headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user_email
        assert data["name"] == "Test User"

    async def test_me_rejects_invalid_token(self, client: AsyncClient) -> None:
        response = await client.get("/auth/me", headers={"Authorization": "Bearer invalid"})
        assert response.status_code == 401

    async def test_me_rejects_expired_token(self, client: AsyncClient) -> None:
        # Create an expired token
        expired_token = create_access_token(uuid.uuid4(), expires_in=timedelta(seconds=-1))
        response = await client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert response.status_code == 401


class TestAuthTokenValidation:
    """Tests for token validation edge cases."""

    async def test_tampered_token_rejected(self, client: AsyncClient) -> None:
        token = create_access_token(uuid.uuid4())
        # Tamper with the signature
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        response = await client.get("/auth/me", headers={"Authorization": f"Bearer {tampered}"})
        assert response.status_code == 401

    async def test_token_with_wrong_secret_rejected(self, client: AsyncClient) -> None:
        forged = create_access_token(uuid.uuid4())
        # Re-sign with a different secret (simulating an attacker)
        from app.core.config import get_settings

        settings = get_settings()
        import jwt

        forged = jwt.encode(
            {"sub": str(uuid.uuid4()), "typ": "access", "iat": 0, "exp": 9999999999, "jti": "x"},
            "attacker-secret-long-enough-for-hs256",
            algorithm=settings.JWT_ALGORITHM,
        )
        response = await client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})
        assert response.status_code == 401

    async def test_alg_none_rejected(self, client: AsyncClient) -> None:
        import jwt
        from app.core.config import get_settings

        settings = get_settings()
        forged = jwt.encode(
            {"sub": str(uuid.uuid4()), "typ": "access", "iat": 0, "exp": 9999999999, "jti": "x"},
            key="",
            algorithm="none",
        )
        response = await client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})
        assert response.status_code == 401

    async def test_non_access_token_type_rejected(self, client: AsyncClient) -> None:
        import jwt
        from app.core.config import get_settings

        settings = get_settings()
        other = jwt.encode(
            {"sub": str(uuid.uuid4()), "typ": "refresh", "iat": 0, "exp": 9999999999, "jti": "x"},
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )
        response = await client.get("/auth/me", headers={"Authorization": f"Bearer {other}"})
        assert response.status_code == 401


class TestAuthSessionIsolation:
    """Tests for multi-user session isolation."""

    async def test_users_cannot_access_each_others_data(
        self, client: AsyncClient
    ) -> None:
        email1 = f"user1_{uuid.uuid4().hex[:8]}@example.com"
        email2 = f"user2_{uuid.uuid4().hex[:8]}@example.com"
        password = "TestPass123!"

        # Register user 1
        await client.post("/auth/register", json={"email": email1, "password": password, "name": "User 1"})
        # Register user 2
        await client.post("/auth/register", json={"email": email2, "password": password, "name": "User 2"})

        # Login as user 1
        login1 = await client.post("/auth/login", json={"email": email1, "password": password})
        token1 = login1.json()["access_token"]

        # Login as user 2 (in same client, different session)
        client2 = AsyncClient(
            transport=client._transport, base_url="http://test"
        )
        login2 = await client2.post("/auth/login", json={"email": email2, "password": password})
        token2 = login2.json()["access_token"]

        # Each token should only return its own user
        me1 = await client.get("/auth/me", headers={"Authorization": f"Bearer {token1}"})
        assert me1.json()["email"] == email1

        me2 = await client2.get("/auth/me", headers={"Authorization": f"Bearer {token2}"})
        assert me2.json()["email"] == email2

        await client2.aclose()


class TestAuthCookieSecurity:
    """Tests for refresh cookie security attributes."""

    async def test_refresh_cookie_is_httponly(
        self, client: AsyncClient, test_user_email: str, test_user_password: str
    ) -> None:
        response = await client.post(
            "/auth/register",
            json={"email": test_user_email, "password": test_user_password, "name": "Test"},
        )
        # Check cookie attributes via Set-Cookie header
        set_cookie = response.headers.get("set-cookie", "")
        assert "httponly" in set_cookie.lower()

    async def test_refresh_cookie_has_correct_path(
        self, client: AsyncClient, test_user_email: str, test_user_password: str
    ) -> None:
        response = await client.post(
            "/auth/register",
            json={"email": test_user_email, "password": test_user_password, "name": "Test"},
        )
        set_cookie = response.headers.get("set-cookie", "")
        assert "path=/auth" in set_cookie.lower()

    async def test_refresh_cookie_samesite_lax(
        self, client: AsyncClient, test_user_email: str, test_user_password: str
    ) -> None:
        response = await client.post(
            "/auth/register",
            json={"email": test_user_email, "password": test_user_password, "name": "Test"},
        )
        set_cookie = response.headers.get("set-cookie", "")
        assert "samesite=lax" in set_cookie.lower()


class TestRefreshTokenDatabase:
    """Tests that verify refresh token database operations."""

    async def test_refresh_token_stored_hashed(
        self, client: AsyncClient, db_session, test_user_email: str, test_user_password: str
    ) -> None:
        await client.post(
            "/auth/register",
            json={"email": test_user_email, "password": test_user_password, "name": "Test"},
        )

        # Check that the token in DB is hashed, not plaintext
        from sqlalchemy import select

        result = await db_session.execute(select(RefreshToken))
        tokens = result.scalars().all()
        assert len(tokens) == 1
        token_row = tokens[0]
        # The token_hash should be a SHA-256 hex digest (64 chars)
        assert len(token_row.token_hash) == 64
        assert all(c in "0123456789abcdef" for c in token_row.token_hash)

    async def test_refresh_token_revoked_on_logout(
        self, client: AsyncClient, db_session, test_user_email: str, test_user_password: str
    ) -> None:
        await client.post(
            "/auth/register",
            json={"email": test_user_email, "password": test_user_password, "name": "Test"},
        )
        await client.post("/auth/logout")

        from sqlalchemy import select

        result = await db_session.execute(select(RefreshToken))
        tokens = result.scalars().all()
        assert len(tokens) == 1
        assert tokens[0].revoked_at is not None