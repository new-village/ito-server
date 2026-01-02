"""Tests for the Authentication API endpoints."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

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
