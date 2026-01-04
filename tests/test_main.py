"""Tests for the main application endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestRootEndpoint:
    """Tests for the root endpoint."""

    @pytest.mark.asyncio
    async def test_root_returns_api_info(self, test_client):
        """Test that root endpoint returns API information."""
        response = await test_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert data["name"] == "NVV Backend"
        assert data["docs"] == "/docs"


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_returns_status(self, test_client):
        """Test that health endpoint returns status information."""
        with patch("app.main.Neo4jConnection.verify_connectivity", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = True

            response = await test_client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "database" in data
            assert "version" in data

    @pytest.mark.asyncio
    async def test_health_check_degraded_when_db_disconnected(self, test_client):
        """Test that health returns degraded status when DB is disconnected."""
        with patch("app.main.Neo4jConnection.verify_connectivity", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = False

            response = await test_client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert data["database"] == "disconnected"


class TestLivenessEndpoint:
    """Tests for the liveness check endpoint."""

    @pytest.mark.asyncio
    async def test_liveness_check(self, test_client):
        """Test that liveness endpoint returns alive status."""
        response = await test_client.get("/live")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"


class TestReadinessEndpoint:
    """Tests for the readiness check endpoint."""

    @pytest.mark.asyncio
    async def test_readiness_check_ready(self, test_client):
        """Test that readiness endpoint returns ready when DB is connected."""
        with patch("app.main.Neo4jConnection.verify_connectivity", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = True

            response = await test_client.get("/ready")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"

    @pytest.mark.asyncio
    async def test_readiness_check_not_ready(self, test_client):
        """Test that readiness endpoint returns not ready when DB is disconnected."""
        with patch("app.main.Neo4jConnection.verify_connectivity", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = False

            response = await test_client.get("/ready")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "not ready"
