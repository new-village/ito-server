"""Search API router for finding nodes by properties."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.neo4j import get_session
from app.models import (
    GraphNode,
    NodeLabel,
    SearchResponse,
)
from app.models.user import User
from app.auth.dependencies import get_current_active_user

router = APIRouter(prefix="/search", tags=["search"])


def _neo4j_node_to_graph_node(record: dict, node_key: str = "n") -> GraphNode:
    """Convert a Neo4j node record to a GraphNode model."""
    node = record[node_key]
    
    # Handle both Neo4j Node objects and dict representations
    if hasattr(node, 'labels'):
        # Neo4j Node object
        properties = dict(node)
        node_id = properties.pop("node_id", 0)
        labels = list(node.labels)
        label = labels[0] if labels else "Unknown"
        element_id = node.element_id
    else:
        # Dict representation (from .data() method)
        properties = dict(node)
        node_id = properties.pop("node_id", 0)
        # Get label and element_id from the record (returned by query)
        label = record.get("_label", "Unknown")
        element_id = record.get("_element_id", str(node_id))

    return GraphNode(
        id=element_id,
        node_id=node_id,
        label=label,
        properties=properties,
    )


@router.get(
    "",
    response_model=SearchResponse,
    summary="Search nodes across all labels",
    description="Search for nodes by node_id or name across all node labels. Requires authentication.",
)
async def search_all(
    current_user: Annotated[User, Depends(get_current_active_user)],
    node_id: int | None = Query(None, description="Search by node_id (exact match)"),
    name: str | None = Query(None, min_length=1, description="Search by name (partial match, case-insensitive)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip for pagination"),
) -> SearchResponse:
    """Search for nodes across all labels.

    Args:
        current_user: The authenticated user (injected by dependency).
        node_id: Search by node_id (exact match).
        name: Search by name (partial match, case-insensitive).
        limit: Maximum number of results to return.
        offset: Number of results to skip for pagination.

    Returns:
        SearchResponse with matching nodes.

    Raises:
        HTTPException: If neither node_id nor name is provided.
    """
    if node_id is None and name is None:
        raise HTTPException(
            status_code=400,
            detail="At least one search parameter (node_id or name) is required"
        )

    if node_id is not None:
        query = """
        MATCH (n) WHERE n.node_id = $node_id 
        RETURN n, labels(n)[0] AS _label, elementId(n) AS _element_id 
        SKIP $offset LIMIT $limit
        """
        params = {"node_id": node_id, "limit": limit, "offset": offset}
    else:
        query = """
        MATCH (n)
        WHERE n.name IS NOT NULL AND toLower(n.name) CONTAINS toLower($name)
        RETURN n, labels(n)[0] AS _label, elementId(n) AS _element_id
        SKIP $offset LIMIT $limit
        """
        params = {"name": name, "limit": limit, "offset": offset}

    async with get_session() as session:
        result = await session.run(query, params)
        records = await result.data()

    nodes = [_neo4j_node_to_graph_node(record) for record in records]

    return SearchResponse(nodes=nodes, total=len(nodes))



@router.get(
    "/{label}",
    response_model=SearchResponse,
    summary="Search nodes by specific label",
    description="Search for nodes by node_id or name within a specific label. Requires authentication.",
)
async def search_by_label(
    label: NodeLabel,
    current_user: Annotated[User, Depends(get_current_active_user)],
    node_id: int | None = Query(None, description="Search by node_id (exact match)"),
    name: str | None = Query(None, min_length=1, description="Search by name (partial match, case-insensitive)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip for pagination"),
) -> SearchResponse:
    """Search for nodes within a specific label.

    Args:
        label: Node label to search within.
        current_user: The authenticated user (injected by dependency).
        node_id: Search by node_id (exact match).
        name: Search by name (partial match, case-insensitive).
        limit: Maximum number of results to return.
        offset: Number of results to skip for pagination.

    Returns:
        SearchResponse with matching nodes.

    Raises:
        HTTPException: If neither node_id nor name is provided.
    """
    if node_id is None and name is None:
        raise HTTPException(
            status_code=400,
            detail="At least one search parameter (node_id or name) is required"
        )

    if node_id is not None:
        query = f"""
        MATCH (n:`{label.value}`) WHERE n.node_id = $node_id 
        RETURN n, labels(n)[0] AS _label, elementId(n) AS _element_id 
        SKIP $offset LIMIT $limit
        """
        params = {"node_id": node_id, "limit": limit, "offset": offset}
    else:
        query = f"""
        MATCH (n:`{label.value}`)
        WHERE n.name IS NOT NULL AND toLower(n.name) CONTAINS toLower($name)
        RETURN n, labels(n)[0] AS _label, elementId(n) AS _element_id
        SKIP $offset LIMIT $limit
        """
        params = {"name": name, "limit": limit, "offset": offset}

    async with get_session() as session:
        result = await session.run(query, params)
        records = await result.data()

    nodes = [_neo4j_node_to_graph_node(record) for record in records]

    return SearchResponse(nodes=nodes, total=len(nodes))
