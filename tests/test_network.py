"""Tests for the Network Traversal API endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def create_mock_path(nodes, relationships):
    """Create a mock Neo4j path object."""
    mock_path = MagicMock()
    mock_path.nodes = nodes
    mock_path.relationships = relationships
    return mock_path


def create_mock_node(element_id, labels, properties):
    """Create a mock Neo4j node."""
    mock_node = MagicMock()
    mock_node.element_id = element_id
    mock_node.labels = frozenset(labels)

    def mock_items():
        return properties.items()

    mock_node.items = mock_items
    return mock_node


def create_mock_relationship(element_id, rel_type, start_node, end_node, properties):
    """Create a mock Neo4j relationship."""
    mock_rel = MagicMock()
    mock_rel.element_id = element_id
    mock_rel.type = rel_type
    mock_rel.start_node = start_node
    mock_rel.end_node = end_node

    def mock_items():
        return properties.items()

    mock_rel.items = mock_items
    return mock_rel


class AsyncIterator:
    """Helper class to create async iterator from a list."""

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


def create_async_result(records):
    """Create a mock async result that supports async iteration."""
    mock_result = MagicMock()
    mock_result.data = AsyncMock(return_value=records)
    mock_result.__aiter__ = lambda self: AsyncIterator(records).__aiter__()
    return mock_result


class TestGetNeighbors:
    """Tests for the get neighbors endpoint."""

    @pytest.mark.asyncio
    async def test_get_neighbors(self, test_client):
        """Test getting neighbors of a node."""
        node1 = create_mock_node("4:test:1", ["entity"], {"node_id": 12345, "name": "Company A"})
        node2 = create_mock_node("4:test:2", ["officer"], {"node_id": 12346, "name": "Person B"})
        rel = create_mock_relationship("5:test:1", "役員", node2, node1, {})

        mock_result = MagicMock()
        mock_result.data = AsyncMock(return_value=[{"start": node1, "r": rel, "neighbor": node2}])

        mock_session = MagicMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.close = AsyncMock()

        with patch("app.routers.network.get_session") as mock_get_session:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_context

            response = await test_client.get("/api/v1/network/neighbors/12345")

            assert response.status_code == 200
            data = response.json()
            assert "nodes" in data
            assert "links" in data
            assert len(data["nodes"]) == 2
            assert len(data["links"]) == 1

    @pytest.mark.asyncio
    async def test_get_neighbors_with_label_filter(self, test_client):
        """Test getting neighbors filtered by label."""
        node1 = create_mock_node("4:test:1", ["entity"], {"node_id": 12345, "name": "Company A"})
        node2 = create_mock_node("4:test:2", ["officer"], {"node_id": 12346, "name": "Person B"})
        rel = create_mock_relationship("5:test:1", "役員", node2, node1, {})

        mock_result = MagicMock()
        mock_result.data = AsyncMock(return_value=[{"start": node1, "r": rel, "neighbor": node2}])

        mock_session = MagicMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.close = AsyncMock()

        with patch("app.routers.network.get_session") as mock_get_session:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_context

            response = await test_client.get("/api/v1/network/neighbors/12345?label=officer")

            assert response.status_code == 200
            data = response.json()
            assert "nodes" in data
            assert "links" in data

    @pytest.mark.asyncio
    async def test_get_neighbors_node_not_found(self, test_client):
        """Test getting neighbors of a non-existent node."""
        # First query returns no results
        mock_result = MagicMock()
        mock_result.data = AsyncMock(return_value=[])

        # Check query also returns no results
        mock_check_result = MagicMock()
        mock_check_result.data = AsyncMock(return_value=[])

        mock_session = MagicMock()
        mock_session.run = AsyncMock(side_effect=[mock_result, mock_check_result])
        mock_session.close = AsyncMock()

        with patch("app.routers.network.get_session") as mock_get_session:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_context

            response = await test_client.get("/api/v1/network/neighbors/99999999")

            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_neighbors_no_neighbors_with_label(self, test_client):
        """Test getting neighbors when node exists but has no neighbors with specified label."""
        node1 = create_mock_node("4:test:1", ["entity"], {"node_id": 12345, "name": "Company A"})

        # First query returns no results (no neighbors with label)
        mock_result = MagicMock()
        mock_result.data = AsyncMock(return_value=[])

        # Check query returns the node (node exists)
        mock_check_result = MagicMock()
        mock_check_result.data = AsyncMock(return_value=[{"n": node1}])

        mock_session = MagicMock()
        mock_session.run = AsyncMock(side_effect=[mock_result, mock_check_result])
        mock_session.close = AsyncMock()

        with patch("app.routers.network.get_session") as mock_get_session:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_context

            response = await test_client.get("/api/v1/network/neighbors/12345?label=intermediary")

            assert response.status_code == 404
            assert "no neighbors with label" in response.json()["detail"]


class TestShortestPath:
    """Tests for the shortest path endpoint."""

    @pytest.mark.asyncio
    async def test_find_shortest_path(self, test_client):
        """Test finding shortest path between two nodes."""
        node1 = create_mock_node("4:test:1", ["entity"], {"node_id": 12345, "name": "Company A"})
        node2 = create_mock_node("4:test:2", ["officer"], {"node_id": 12346, "name": "Person B"})
        rel = create_mock_relationship("5:test:1", "役員", node2, node1, {})
        mock_path = create_mock_path([node1, node2], [rel])

        # Create mock record that supports .get()
        mock_record = MagicMock()
        mock_record.get = MagicMock(side_effect=lambda k: mock_path if k == "path" else None)

        mock_result = create_async_result([mock_record])

        mock_session = MagicMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.close = AsyncMock()

        with patch("app.routers.network.get_session") as mock_get_session:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_context

            response = await test_client.get(
                "/api/v1/network/shortest-path?start_node_id=12345&end_node_id=12346"
            )

            assert response.status_code == 200
            data = response.json()
            assert "nodes" in data
            assert "links" in data

    @pytest.mark.asyncio
    async def test_shortest_path_not_found(self, test_client):
        """Test when no path exists between nodes."""
        mock_result = create_async_result([])

        mock_session = MagicMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.close = AsyncMock()

        with patch("app.routers.network.get_session") as mock_get_session:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_context

            response = await test_client.get(
                "/api/v1/network/shortest-path?start_node_id=12345&end_node_id=99999"
            )

            assert response.status_code == 404


class TestGetRelationshipTypes:
    """Tests for the get relationship types endpoint."""

    @pytest.mark.asyncio
    async def test_get_relationship_types(self, test_client):
        """Test getting available relationship types."""
        response = await test_client.get("/api/v1/network/relationship-types")

        assert response.status_code == 200
        data = response.json()
        assert "relationship_types" in data
        assert len(data["relationship_types"]) == 6  # 6 relationship types in schema
