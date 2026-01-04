"""Tests for the Search API endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSearchAll:
    """Tests for the search all labels endpoint."""

    @pytest.mark.asyncio
    async def test_search_by_node_id(self, authenticated_test_client, mock_neo4j_node):
        """Test searching by node_id across all labels."""
        mock_result = MagicMock()
        mock_result.data = AsyncMock(return_value=[{"n": mock_neo4j_node}])

        mock_session = MagicMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.close = AsyncMock()

        with patch("app.routers.search.get_session") as mock_get_session:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_context

            response = await authenticated_test_client.get("/api/v1/search?node_id=12345")

            assert response.status_code == 200
            data = response.json()
            assert "nodes" in data
            assert "total" in data

    @pytest.mark.asyncio
    async def test_search_by_name(self, authenticated_test_client, mock_neo4j_node):
        """Test searching by name across all labels."""
        mock_result = MagicMock()
        mock_result.data = AsyncMock(return_value=[{"n": mock_neo4j_node}])

        mock_session = MagicMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.close = AsyncMock()

        with patch("app.routers.search.get_session") as mock_get_session:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_context

            response = await authenticated_test_client.get("/api/v1/search?name=Test")

            assert response.status_code == 200
            data = response.json()
            assert "nodes" in data
            assert "total" in data

    @pytest.mark.asyncio
    async def test_search_requires_parameter(self, authenticated_test_client):
        """Test that at least one search parameter is required."""
        response = await authenticated_test_client.get("/api/v1/search")

        assert response.status_code == 400
        data = response.json()
        assert "required" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_search_not_found(self, authenticated_test_client):
        """Test searching for non-existent node."""
        mock_result = MagicMock()
        mock_result.data = AsyncMock(return_value=[])

        mock_session = MagicMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.close = AsyncMock()

        with patch("app.routers.search.get_session") as mock_get_session:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_context

            response = await authenticated_test_client.get("/api/v1/search?node_id=99999999")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0
            assert data["nodes"] == []

    @pytest.mark.asyncio
    async def test_search_requires_auth(self, test_client):
        """Test that search endpoint requires authentication."""
        response = await test_client.get("/api/v1/search?node_id=12345")
        assert response.status_code == 401


class TestSearchByLabel:
    """Tests for the search by specific label endpoint."""

    @pytest.mark.asyncio
    async def test_search_entity_by_node_id(self, authenticated_test_client, mock_neo4j_node):
        """Test searching entity by node_id."""
        mock_result = MagicMock()
        mock_result.data = AsyncMock(return_value=[{"n": mock_neo4j_node}])

        mock_session = MagicMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.close = AsyncMock()

        with patch("app.routers.search.get_session") as mock_get_session:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_context

            response = await authenticated_test_client.get("/api/v1/search/entity?node_id=12345")

            assert response.status_code == 200
            data = response.json()
            assert "nodes" in data
            assert "total" in data

    @pytest.mark.asyncio
    async def test_search_officer_by_name(self, authenticated_test_client, mock_neo4j_node):
        """Test searching officer by name."""
        mock_result = MagicMock()
        mock_result.data = AsyncMock(return_value=[{"n": mock_neo4j_node}])

        mock_session = MagicMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.close = AsyncMock()

        with patch("app.routers.search.get_session") as mock_get_session:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_context

            response = await authenticated_test_client.get("/api/v1/search/intermediary?name=John")

            assert response.status_code == 200
            data = response.json()
            assert "nodes" in data

    @pytest.mark.asyncio
    async def test_search_label_requires_parameter(self, authenticated_test_client):
        """Test that at least one search parameter is required for label search."""
        response = await authenticated_test_client.get("/api/v1/search/entity")

        assert response.status_code == 400
        data = response.json()
        assert "required" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_search_invalid_label(self, authenticated_test_client):
        """Test that invalid labels are rejected."""
        response = await authenticated_test_client.get("/api/v1/search/invalid_label?node_id=12345")

        assert response.status_code == 422  # Validation error


