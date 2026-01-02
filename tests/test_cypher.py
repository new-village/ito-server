"""Tests for the Cypher API endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestExecuteCypher:
    """Tests for the execute Cypher endpoint."""

    @pytest.mark.asyncio
    async def test_execute_valid_query(self, authenticated_test_client):
        """Test executing a valid Cypher query."""

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
                json={"query": "MATCH (n) RETURN count(n) AS count"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            assert "count" in data
            assert "keys" in data

    @pytest.mark.asyncio
    async def test_execute_empty_query(self, authenticated_test_client):
        """Test that empty queries are rejected."""
        response = await authenticated_test_client.post(
            "/api/v1/cypher/execute",
            json={"query": ""}
        )

        assert response.status_code == 400
        data = response.json()
        assert "empty" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_execute_with_parameters(self, authenticated_test_client):
        """Test executing query with parameters."""

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
        mock_result.keys = MagicMock(return_value=["n"])
        mock_result.__aiter__ = lambda self: MockAsyncIterator([])

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
                json={
                    "query": "MATCH (n {node_id: $id}) RETURN n",
                    "parameters": {"id": 12345}
                }
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_execute_dangerous_query_rejected(self, authenticated_test_client):
        """Test that dangerous queries are rejected."""
        dangerous_queries = [
            "DELETE n",
            "MATCH (n) DELETE n",
            "DROP INDEX my_index",
        ]

        for query in dangerous_queries:
            response = await authenticated_test_client.post(
                "/api/v1/cypher/execute",
                json={"query": query}
            )

            assert response.status_code == 403, f"Query should be rejected: {query}"

    @pytest.mark.asyncio
    async def test_execute_requires_auth(self, test_client):
        """Test that execute endpoint requires authentication."""
        response = await test_client.post(
            "/api/v1/cypher/execute",
            json={"query": "MATCH (n) RETURN n LIMIT 1"}
        )

        assert response.status_code == 401


class TestGetSchema:
    """Tests for the get schema endpoint."""

    @pytest.mark.asyncio
    async def test_get_schema(self, test_client):
        """Test getting database schema."""

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

        mock_labels_result = MagicMock()
        mock_labels_result.__aiter__ = lambda self: MockAsyncIterator([
            {"label": "entity"}, {"label": "officer"}
        ])

        mock_rels_result = MagicMock()
        mock_rels_result.__aiter__ = lambda self: MockAsyncIterator([
            {"relationshipType": "officer_of"}
        ])

        mock_props_result = MagicMock()
        mock_props_result.__aiter__ = lambda self: MockAsyncIterator([
            {"propertyKey": "name"}
        ])

        mock_session = MagicMock()
        mock_session.run = AsyncMock(side_effect=[
            mock_labels_result,
            mock_rels_result,
            mock_props_result
        ])
        mock_session.close = AsyncMock()

        with patch("app.routers.cypher.get_session") as mock_get_session:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_context

            response = await test_client.get("/api/v1/cypher/schema")

            assert response.status_code == 200
            data = response.json()
            assert "node_labels" in data
            assert "relationship_types" in data
            assert "property_keys" in data


class TestGetStats:
    """Tests for the get statistics endpoint."""

    @pytest.mark.asyncio
    async def test_get_stats(self, test_client):
        """Test getting database statistics."""
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, key: {"nodeCount": 1000, "relationshipCount": 5000}[key]

        mock_result = MagicMock()
        mock_result.single = AsyncMock(return_value=mock_record)

        mock_session = MagicMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.close = AsyncMock()

        with patch("app.routers.cypher.get_session") as mock_get_session:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_context

            response = await test_client.get("/api/v1/cypher/stats")

            assert response.status_code == 200
            data = response.json()
            assert "node_count" in data
            assert "relationship_count" in data
