"""Neo4j database connection management.

Implements a singleton driver pattern using FastAPI's lifespan context manager.
Uses the official neo4j Python driver with AsyncGraphDatabase.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from neo4j import AsyncGraphDatabase, AsyncDriver

from app.config import get_settings


class Neo4jConnection:
    """Singleton Neo4j connection manager."""

    _driver: AsyncDriver | None = None

    @classmethod
    async def get_driver(cls) -> AsyncDriver:
        """Get or create the Neo4j driver instance."""
        if cls._driver is None:
            settings = get_settings()
            cls._driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URL,
                auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
            )
        return cls._driver

    @classmethod
    async def close(cls) -> None:
        """Close the Neo4j driver connection."""
        if cls._driver is not None:
            await cls._driver.close()
            cls._driver = None

    @classmethod
    async def verify_connectivity(cls) -> bool:
        """Verify the database connection is working."""
        driver = await cls.get_driver()
        try:
            await driver.verify_connectivity()
            return True
        except Exception:
            return False


@asynccontextmanager
async def get_session() -> AsyncGenerator:
    """Get a Neo4j session for database operations.

    Usage:
        async with get_session() as session:
            result = await session.run("MATCH (n) RETURN n LIMIT 1")
    """
    driver = await Neo4jConnection.get_driver()
    session = driver.session()
    try:
        yield session
    finally:
        await session.close()


async def execute_query(query: str, parameters: dict | None = None) -> list[dict]:
    """Execute a Cypher query and return results as a list of dictionaries.

    Args:
        query: The Cypher query to execute.
        parameters: Optional parameters for the query.

    Returns:
        List of dictionaries containing the query results.
    """
    async with get_session() as session:
        result = await session.run(query, parameters or {})
        records = await result.data()
        return records


async def execute_query_single(query: str, parameters: dict | None = None) -> dict | None:
    """Execute a Cypher query and return a single result.

    Args:
        query: The Cypher query to execute.
        parameters: Optional parameters for the query.

    Returns:
        A dictionary containing the single result, or None if no results.
    """
    async with get_session() as session:
        result = await session.run(query, parameters or {})
        record = await result.single()
        return dict(record) if record else None
