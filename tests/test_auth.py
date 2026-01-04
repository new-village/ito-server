"""Tests for the Authentication API endpoints."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone

from sqlmodel import Session


class TestPasswordHashing:
    """Tests for password hashing utilities."""

    def test_password_hash_and_verify(self):
        """Test that passwords are correctly hashed and verified."""
        from app.auth.security import get_password_hash, verify_password

        password = "mysecretpassword"
        hashed = get_password_hash(password)

        # Hash should not be the same as the original password
        assert hashed != password

        # Should verify correctly
        assert verify_password(password, hashed) is True

        # Wrong password should not verify
        assert verify_password("wrongpassword", hashed) is False

    def test_password_hash_is_different_each_time(self):
        """Test that hashing the same password produces different hashes (salt)."""
        from app.auth.security import get_password_hash

        password = "mysecretpassword"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        # Due to salting, each hash should be different
        assert hash1 != hash2


class TestJWTTokens:
    """Tests for JWT token utilities."""

    def test_create_and_decode_token(self):
        """Test creating and decoding JWT tokens."""
        from app.auth.security import create_access_token, decode_access_token

        data = {"sub": "testuser", "is_admin": True}
        token = create_access_token(data)

        decoded = decode_access_token(token)
        assert decoded is not None
        assert decoded["sub"] == "testuser"
        assert decoded["is_admin"] is True
        assert "exp" in decoded

    def test_decode_invalid_token(self):
        """Test decoding an invalid token returns None."""
        from app.auth.security import decode_access_token

        decoded = decode_access_token("invalid_token")
        assert decoded is None

    def test_token_with_custom_expiry(self):
        """Test creating token with custom expiry time."""
        from datetime import timedelta
        from app.auth.security import create_access_token, decode_access_token

        data = {"sub": "testuser"}
        token = create_access_token(data, expires_delta=timedelta(hours=1))

        decoded = decode_access_token(token)
        assert decoded is not None
        assert decoded["sub"] == "testuser"


class TestRefreshTokenUtilities:
    """Tests for refresh token utilities."""

    def test_generate_refresh_token(self):
        """Test generating refresh tokens."""
        from app.auth.security import generate_refresh_token

        token1 = generate_refresh_token()
        token2 = generate_refresh_token()

        # Tokens should be unique
        assert token1 != token2

        # Tokens should be reasonably long
        assert len(token1) >= 32

    def test_hash_refresh_token(self):
        """Test hashing refresh tokens."""
        from app.auth.security import generate_refresh_token, hash_refresh_token

        token = generate_refresh_token()
        hash1 = hash_refresh_token(token)
        hash2 = hash_refresh_token(token)

        # Same token should produce same hash (deterministic)
        assert hash1 == hash2

        # Different tokens should produce different hashes
        token2 = generate_refresh_token()
        hash3 = hash_refresh_token(token2)
        assert hash1 != hash3


class TestLoginEndpoint:
    """Tests for the /login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success(self, test_client, test_db_session, test_user):
        """Test successful login returns both access and refresh tokens."""
        response = await test_client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": "testpassword123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, test_client, test_user):
        """Test login with wrong password fails."""
        response = await test_client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": "wrongpassword"},
        )

        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, test_client):
        """Test login with nonexistent user fails."""
        response = await test_client.post(
            "/api/v1/auth/login",
            data={"username": "nonexistent", "password": "somepassword"},
        )

        assert response.status_code == 401


class TestRefreshEndpoint:
    """Tests for the /refresh endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_success(self, test_client, test_user):
        """Test refreshing tokens with valid refresh token."""
        # First, login to get tokens
        login_response = await test_client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": "testpassword123"},
        )
        tokens = login_response.json()

        # Use refresh token to get new tokens
        refresh_response = await test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )

        assert refresh_response.status_code == 200
        new_tokens = refresh_response.json()
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens
        # Refresh token should be rotated (different from original)
        assert new_tokens["refresh_token"] != tokens["refresh_token"]

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, test_client):
        """Test refresh with invalid token fails."""
        response = await test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid_refresh_token"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_rotation_invalidates_old(self, test_client, test_user):
        """Test that using a refresh token invalidates it (can only be used once)."""
        # Login to get tokens
        login_response = await test_client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": "testpassword123"},
        )
        tokens = login_response.json()

        # Use refresh token
        await test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )

        # Try to use the same refresh token again - should fail
        second_response = await test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )

        assert second_response.status_code == 401


class TestLogoutEndpoint:
    """Tests for the /logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout_success(self, test_client, test_user):
        """Test logout invalidates refresh token."""
        # Login to get tokens
        login_response = await test_client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": "testpassword123"},
        )
        tokens = login_response.json()

        # Logout
        logout_response = await test_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": tokens["refresh_token"]},
        )

        assert logout_response.status_code == 200
        assert "Successfully logged out" in logout_response.json()["message"]

        # Try to use the refresh token - should fail
        refresh_response = await test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )

        assert refresh_response.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_invalid_token_still_succeeds(self, test_client):
        """Test logout with invalid token still returns success (security)."""
        response = await test_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": "invalid_token"},
        )

        # Should still return success to not reveal if token existed
        assert response.status_code == 200


class TestLogoutAllEndpoint:
    """Tests for the /logout-all endpoint."""

    @pytest.mark.asyncio
    async def test_logout_all_success(self, test_client, test_user):
        """Test logout-all invalidates all sessions."""
        # Login twice to create multiple sessions
        login1 = await test_client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": "testpassword123"},
        )
        tokens1 = login1.json()

        login2 = await test_client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": "testpassword123"},
        )
        tokens2 = login2.json()

        # Use first access token to logout all
        logout_response = await test_client.post(
            "/api/v1/auth/logout-all",
            headers={"Authorization": f"Bearer {tokens1['access_token']}"},
        )

        assert logout_response.status_code == 200
        assert "2 session(s)" in logout_response.json()["message"]

        # Both refresh tokens should be invalid now
        refresh1 = await test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens1["refresh_token"]},
        )
        assert refresh1.status_code == 401

        refresh2 = await test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens2["refresh_token"]},
        )
        assert refresh2.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_all_requires_auth(self, test_client):
        """Test logout-all requires authentication."""
        response = await test_client.post("/api/v1/auth/logout-all")
        assert response.status_code == 401


class TestMeEndpoint:
    """Tests for the /me endpoint."""

    @pytest.mark.asyncio
    async def test_get_me_no_token(self, test_client):
        """Test getting current user without authentication."""
        response = await test_client.get("/api/v1/auth/me")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_invalid_token(self, test_client):
        """Test getting current user with invalid token."""
        response = await test_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_authenticated(self, authenticated_test_client, mock_authenticated_user):
        """Test getting current user info with valid authentication."""
        response = await authenticated_test_client.get("/api/v1/auth/me")

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == mock_authenticated_user.username


class TestProtectedEndpoints:
    """Tests for endpoints protected by authentication."""

    @pytest.mark.asyncio
    async def test_cypher_execute_requires_auth(self, test_client):
        """Test that /cypher/execute requires authentication."""
        response = await test_client.post(
            "/api/v1/cypher/execute",
            json={"query": "MATCH (n) RETURN n LIMIT 1"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_cypher_execute_with_auth(self, authenticated_test_client):
        """Test that authenticated users can access cypher endpoint."""
        from unittest.mock import AsyncMock

        class MockAsyncIterator:
            def __init__(self, items):
                self.items = items
                self.index = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index >= len(self.items):
                    raise StopAsyncIteration
                item = self.items[self.index]
                self.index += 1
                return item

        mock_result = MagicMock()
        mock_result.keys = MagicMock(return_value=["count"])
        mock_result.__aiter__ = lambda self: MockAsyncIterator([{"count": 100}])

        mock_session = MagicMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.close = AsyncMock()

        with patch("app.routers.cypher.get_session") as mock_get_session:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_context

            response = await authenticated_test_client.post(
                "/api/v1/cypher/execute",
                json={"query": "MATCH (n) RETURN count(n) AS count"},
            )

            # Should succeed (not 401)
            assert response.status_code == 200
