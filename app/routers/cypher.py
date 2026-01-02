"""Async Cypher Query API router for executing arbitrary queries."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.db.neo4j import get_session
from app.models.user import User
from app.auth.dependencies import get_current_active_user

router = APIRouter(prefix="/cypher", tags=["cypher"])


class CypherRequest(BaseModel):
    """Request model for Cypher query execution."""

    query: str = Field(..., description="Cypher query to execute")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Query parameters"
    )


class CypherResponse(BaseModel):
    """Response model for Cypher query results."""

    results: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Raw query results"
    )
    count: int = Field(default=0, description="Number of records returned")
    keys: list[str] = Field(default_factory=list, description="Column keys in the result")


def _serialize_neo4j_value(value: Any) -> Any:
    """Serialize Neo4j-specific types to JSON-compatible values.

    Args:
        value: A value from Neo4j query result.

    Returns:
        JSON-serializable value.
    """
    if value is None:
        return None

    # Handle Neo4j Node
    if hasattr(value, 'element_id') and hasattr(value, 'labels'):
        return {
            "_type": "node",
            "element_id": value.element_id,
            "labels": list(value.labels),
            "properties": dict(value),
        }

    # Handle Neo4j Relationship
    if hasattr(value, 'element_id') and hasattr(value, 'type'):
        return {
            "_type": "relationship",
            "element_id": value.element_id,
            "type": value.type,
            "start_node_element_id": value.start_node.element_id if value.start_node else None,
            "end_node_element_id": value.end_node.element_id if value.end_node else None,
            "properties": dict(value),
        }

    # Handle Neo4j Path
    if hasattr(value, 'nodes') and hasattr(value, 'relationships'):
        return {
            "_type": "path",
            "nodes": [_serialize_neo4j_value(n) for n in value.nodes],
            "relationships": [_serialize_neo4j_value(r) for r in value.relationships],
        }

    # Handle lists
    if isinstance(value, list):
        return [_serialize_neo4j_value(v) for v in value]

    # Handle dicts
    if isinstance(value, dict):
        return {k: _serialize_neo4j_value(v) for k, v in value.items()}

    # Return primitive values as-is
    return value


def _serialize_record(record: dict) -> dict:
    """Serialize a Neo4j record to a JSON-compatible dictionary.

    Args:
        record: A record from Neo4j query result.

    Returns:
        JSON-serializable dictionary.
    """
    return {key: _serialize_neo4j_value(value) for key, value in record.items()}


@router.post(
    "/execute",
    response_model=CypherResponse,
    summary="Execute a Cypher query",
    description="Execute an arbitrary Cypher query asynchronously and return raw results. Requires authentication.",
)
async def execute_cypher(
    request: CypherRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> CypherResponse:
    """Execute an arbitrary Cypher query.

    Args:
        request: CypherRequest containing the query and optional parameters.
        current_user: The authenticated user (injected by dependency).

    Returns:
        CypherResponse with raw query results.

    Raises:
        HTTPException: If query execution fails.
    """
    # Basic query validation
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Block potentially dangerous operations in queries
    dangerous_keywords = ["DELETE", "DETACH DELETE", "DROP", "CREATE INDEX", "DROP INDEX", "CREATE CONSTRAINT", "DROP CONSTRAINT"]
    query_upper = query.upper()

    for keyword in dangerous_keywords:
        # Check if keyword appears as a statement (not just in a string)
        if keyword in query_upper:
            # Allow if it's just a MATCH...RETURN query that happens to contain DELETE in a property value
            if not any(query_upper.startswith(k) for k in ["MATCH", "OPTIONAL MATCH", "WITH", "UNWIND", "CALL", "RETURN"]):
                raise HTTPException(
                    status_code=403,
                    detail=f"Query contains forbidden operation: {keyword}. Only read operations are allowed."
                )
            # Additional check for DELETE/DROP as standalone operations
            if keyword in query_upper.split():
                raise HTTPException(
                    status_code=403,
                    detail=f"Query contains forbidden operation: {keyword}. Only read operations are allowed."
                )

    try:
        async with get_session() as session:
            result = await session.run(query, request.parameters)
            keys = list(result.keys())
            records = [_serialize_record(record) async for record in result]

        return CypherResponse(
            results=records,
            count=len(records),
            keys=keys,
        )

    except Exception as e:
        error_message = str(e)
        # Sanitize error message to avoid exposing sensitive information
        if "authentication" in error_message.lower() or "password" in error_message.lower():
            error_message = "Database authentication error"

        raise HTTPException(
            status_code=500,
            detail=f"Query execution failed: {error_message}"
        )


@router.get(
    "/schema",
    summary="Get database schema",
    description="Retrieve the database schema including node labels, relationship types, and properties.",
)
async def get_schema() -> dict:
    """Get the database schema.

    Returns:
        Dictionary containing node labels, relationship types, and their properties.
    """
    # Get node labels
    labels_query = "CALL db.labels()"

    # Get relationship types
    rel_types_query = "CALL db.relationshipTypes()"

    # Get property keys
    property_keys_query = "CALL db.propertyKeys()"

    try:
        async with get_session() as session:
            # Fetch labels
            labels_result = await session.run(labels_query)
            labels = [record["label"] async for record in labels_result]

            # Fetch relationship types
            rel_result = await session.run(rel_types_query)
            relationship_types = [record["relationshipType"] async for record in rel_result]

            # Fetch property keys
            props_result = await session.run(property_keys_query)
            property_keys = [record["propertyKey"] async for record in props_result]

        return {
            "node_labels": labels,
            "relationship_types": relationship_types,
            "property_keys": property_keys,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve schema: {str(e)}"
        )


@router.get(
    "/stats",
    summary="Get database statistics",
    description="Retrieve basic statistics about the database.",
)
async def get_stats() -> dict:
    """Get basic database statistics.

    Returns:
        Dictionary containing node and relationship counts.
    """
    stats_query = """
    MATCH (n)
    WITH count(n) AS nodeCount
    MATCH ()-[r]->()
    RETURN nodeCount, count(r) AS relationshipCount
    """

    try:
        async with get_session() as session:
            result = await session.run(stats_query)
            record = await result.single()

            if record:
                return {
                    "node_count": record["nodeCount"],
                    "relationship_count": record["relationshipCount"],
                }
            else:
                return {
                    "node_count": 0,
                    "relationship_count": 0,
                }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve statistics: {str(e)}"
        )
