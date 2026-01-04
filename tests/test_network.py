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


class AsyncResultIterator:
    """Async iterator that mimics Neo4j Result behavior.
    
    Neo4j's async driver returns results that can be iterated with `async for`.
    Each item is a Record-like object with a .get() method.
    """

    def __init__(self, records: list[dict]):
        self.records = records
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.records):
            raise StopAsyncIteration
        # Create a mock record with .get() method
        record_data = self.records[self.index]
        mock_record = MagicMock()
        mock_record.get = lambda key, default=None: record_data.get(key, default)
        self.index += 1
        return mock_record


def create_mock_neo4j_result(records: list[dict]):
    """Create a mock Neo4j result that supports async iteration.
    
    This mimics the behavior of neo4j.AsyncResult which:
    - Can be iterated with `async for record in result:`
    - Each record has a .get(key) method to retrieve values
    - Also supports .data() for backward compatibility (returns dicts)
    """
    mock_result = MagicMock()
    # Support for result.data() - returns list of dicts
    mock_result.data = AsyncMock(return_value=records)
    # Support for async iteration - returns Record-like objects
    mock_result.__aiter__ = lambda self: AsyncResultIterator(records)
    return mock_result


class TestGetNeighbors:
    """Tests for the get neighbors endpoint."""

    @pytest.mark.asyncio
    async def test_get_neighbors(self, authenticated_test_client):
        """Test getting neighbors of a node."""
        node1 = create_mock_node("4:test:1", ["entity"], {"node_id": 12345, "name": "Company A"})
        node2 = create_mock_node("4:test:2", ["officer"], {"node_id": 12346, "name": "Person B"})
        rel = create_mock_relationship("5:test:1", "役員", node2, node1, {})

        mock_result = create_mock_neo4j_result([{"start": node1, "r": rel, "neighbor": node2}])

        mock_session = MagicMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.close = AsyncMock()

        with patch("app.routers.network.get_session") as mock_get_session:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_context

            response = await authenticated_test_client.get("/api/v1/network/neighbors/12345")

            assert response.status_code == 200
            data = response.json()
            assert "nodes" in data
            assert "links" in data
            assert len(data["nodes"]) == 2
            assert len(data["links"]) == 1

    @pytest.mark.asyncio
    async def test_get_neighbors_with_label_filter(self, authenticated_test_client):
        """Test getting neighbors filtered by label."""
        node1 = create_mock_node("4:test:1", ["entity"], {"node_id": 12345, "name": "Company A"})
        node2 = create_mock_node("4:test:2", ["officer"], {"node_id": 12346, "name": "Person B"})
        rel = create_mock_relationship("5:test:1", "役員", node2, node1, {})

        mock_result = create_mock_neo4j_result([{"start": node1, "r": rel, "neighbor": node2}])

        mock_session = MagicMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.close = AsyncMock()

        with patch("app.routers.network.get_session") as mock_get_session:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_context

            response = await authenticated_test_client.get("/api/v1/network/neighbors/12345?label=officer")

            assert response.status_code == 200
            data = response.json()
            assert "nodes" in data
            assert "links" in data

    @pytest.mark.asyncio
    async def test_get_neighbors_node_not_found(self, authenticated_test_client):
        """Test getting neighbors of a non-existent node returns empty result."""
        # First query returns no results
        mock_result = create_mock_neo4j_result([])

        # Check query also returns no results
        mock_check_result = create_mock_neo4j_result([])

        mock_session = MagicMock()
        mock_session.run = AsyncMock(side_effect=[mock_result, mock_check_result])
        mock_session.close = AsyncMock()

        with patch("app.routers.network.get_session") as mock_get_session:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_context

            response = await authenticated_test_client.get("/api/v1/network/neighbors/99999999")

            assert response.status_code == 200
            data = response.json()
            assert data["nodes"] == []
            assert data["links"] == []

    @pytest.mark.asyncio
    async def test_get_neighbors_no_neighbors_with_label(self, authenticated_test_client):
        """Test getting neighbors when node exists but has no neighbors with specified label."""
        node1 = create_mock_node("4:test:1", ["entity"], {"node_id": 12345, "name": "Company A"})

        # First query returns no results (no neighbors with label)
        mock_result = create_mock_neo4j_result([])

        # Check query returns the node (node exists)
        mock_check_result = create_mock_neo4j_result([{"n": node1}])

        mock_session = MagicMock()
        mock_session.run = AsyncMock(side_effect=[mock_result, mock_check_result])
        mock_session.close = AsyncMock()

        with patch("app.routers.network.get_session") as mock_get_session:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_context

            response = await authenticated_test_client.get("/api/v1/network/neighbors/12345?label=intermediary")

            assert response.status_code == 200
            data = response.json()
            # Node exists but no neighbors with the specified label
            assert len(data["nodes"]) == 1
            assert data["links"] == []

    @pytest.mark.asyncio
    async def test_get_neighbors_includes_falsy_relationship(self, authenticated_test_client):
        """Regression: include links even if Relationship is falsy (e.g., no properties)."""
        node1 = create_mock_node("4:test:1", ["officer"], {"node_id": 12345, "name": "Person A"})
        node2 = create_mock_node("4:test:2", ["address"], {"node_id": 67890, "address": "Somewhere"})
        rel = create_mock_relationship("5:test:1", "所在地", node1, node2, {})
        rel.__bool__.return_value = False

        mock_result = create_mock_neo4j_result([{"start": node1, "r": rel, "neighbor": node2}])

        mock_session = MagicMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.close = AsyncMock()

        with patch("app.routers.network.get_session") as mock_get_session:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_context

            response = await authenticated_test_client.get("/api/v1/network/neighbors/12345")

            assert response.status_code == 200
            data = response.json()
            assert len(data["nodes"]) == 2
            assert len(data["links"]) == 1

    @pytest.mark.asyncio
    async def test_get_neighbors_requires_auth(self, test_client):
        """Test that neighbors endpoint requires authentication."""
        response = await test_client.get("/api/v1/network/neighbors/12345")
        assert response.status_code == 401


class TestShortestPath:
    """Tests for the shortest path endpoint."""

    @pytest.mark.asyncio
    async def test_find_shortest_path_with_default_max_hops(self, authenticated_test_client):
        """Test finding shortest path with default max_hops (4)."""
        node1 = create_mock_node("4:test:1", ["entity"], {"node_id": 12345, "name": "Company A"})
        node2 = create_mock_node("4:test:2", ["officer"], {"node_id": 12346, "name": "Person B"})
        rel = create_mock_relationship("5:test:1", "役員", node2, node1, {})
        mock_path = create_mock_path([node1, node2], [rel])

        mock_result = create_mock_neo4j_result([{"path": mock_path}])

        mock_session = MagicMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.close = AsyncMock()

        with patch("app.routers.network.get_session") as mock_get_session:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_context

            # Call without max_hops - should use default value of 4
            response = await authenticated_test_client.get(
                "/api/v1/network/shortest-path?start_node_id=12345&end_node_id=12346"
            )

            assert response.status_code == 200
            data = response.json()
            assert "nodes" in data
            assert "links" in data

            # Verify the query was called with max_hops=4 in the path pattern
            call_args = mock_session.run.call_args
            query = call_args[0][0]
            assert "[*1..4]" in query

    @pytest.mark.asyncio
    async def test_find_shortest_path_with_custom_max_hops(self, authenticated_test_client):
        """Test finding shortest path with custom max_hops."""
        node1 = create_mock_node("4:test:1", ["entity"], {"node_id": 12345, "name": "Company A"})
        node2 = create_mock_node("4:test:2", ["officer"], {"node_id": 12346, "name": "Person B"})
        rel = create_mock_relationship("5:test:1", "役員", node2, node1, {})
        mock_path = create_mock_path([node1, node2], [rel])

        mock_result = create_mock_neo4j_result([{"path": mock_path}])

        mock_session = MagicMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.close = AsyncMock()

        with patch("app.routers.network.get_session") as mock_get_session:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_context

            # Call with custom max_hops=7
            response = await authenticated_test_client.get(
                "/api/v1/network/shortest-path?start_node_id=12345&end_node_id=12346&max_hops=7"
            )

            assert response.status_code == 200
            data = response.json()
            assert "nodes" in data
            assert "links" in data

            # Verify the query was called with max_hops=7 in the path pattern
            call_args = mock_session.run.call_args
            query = call_args[0][0]
            assert "[*1..7]" in query

    @pytest.mark.asyncio
    async def test_shortest_path_not_found(self, authenticated_test_client):
        """Test when no path exists between nodes returns empty result."""
        mock_result = create_mock_neo4j_result([])

        mock_session = MagicMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.close = AsyncMock()

        with patch("app.routers.network.get_session") as mock_get_session:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_context

            response = await authenticated_test_client.get(
                "/api/v1/network/shortest-path?start_node_id=12345&end_node_id=99999"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["nodes"] == []
            assert data["links"] == []

    @pytest.mark.asyncio
    async def test_shortest_path_requires_auth(self, test_client):
        """Test that shortest-path endpoint requires authentication."""
        response = await test_client.get(
            "/api/v1/network/shortest-path?start_node_id=12345&end_node_id=99999"
        )
        assert response.status_code == 401


class TestGetRelationshipTypes:
    """Tests for the get relationship types endpoint."""

    @pytest.mark.asyncio
    async def test_get_relationship_types(self, authenticated_test_client):
        """Test getting available relationship types."""
        response = await authenticated_test_client.get("/api/v1/network/relationship-types")

        assert response.status_code == 200
        data = response.json()
        assert "relationship_types" in data
        assert len(data["relationship_types"]) == 6  # 6 relationship types in schema

    @pytest.mark.asyncio
    async def test_get_relationship_types_requires_auth(self, test_client):
        """Test that relationship-types endpoint requires authentication."""
        response = await test_client.get("/api/v1/network/relationship-types")
        assert response.status_code == 401
